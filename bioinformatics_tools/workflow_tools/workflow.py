'''
Workflow tools generate
Invoked: $ dane_wf wf: example <params/options/io>
'''
import logging
import re
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path

from bioinformatics_tools.file_classes.base_classes import command
from bioinformatics_tools.workflow_tools.bapptainer import (
    CacheSifError, cache_sif_files)
from bioinformatics_tools.workflow_tools.models import WorkflowKey
from bioinformatics_tools.workflow_tools.output_cache import log_workflow_run, restore_all, store_all
from bioinformatics_tools.workflow_tools.programs import ProgramBase
from bioinformatics_tools.workflow_tools.workflow_registry import WORKFLOWS

LOGGER = logging.getLogger(__name__)
WORKFLOW_DIR = Path(__file__).parent


class WorkflowBase(ProgramBase):
    '''Snakemake workflow execution. Inherits single-program commands from ProgramBase.
    '''

    def __init__(self, workflow_id=None):
        LOGGER.debug('Starting __init__ of WorkflowBase')
        self.workflow_id = workflow_id
        self.timestamp = datetime.now().strftime("%d%m%y-%H%M")

        LOGGER.debug('Using the workflow id of %s', self.workflow_id)

        super().__init__()

    def build_executable(self, key: WorkflowKey, config_dict: dict = None, mode='notdev', compute_config: dict = None) -> list[str]:
        '''
        Build snakemake command from workflow key and config.

        Args:
            key: WorkflowKey defining the workflow
            config_dict: Snakemake config parameters
            mode: Execution mode ('dev' or other for slurm)
            compute_config: Compute cluster config (account, partition, resources)
        '''
        smk_path = WORKFLOW_DIR / key.snakemake_file

        # Use compute config to determine max_jobs (default to 5)
        max_jobs = 5
        if compute_config:
            max_jobs = compute_config.get('max_jobs', 5)

        core_command = [
            'snakemake',
            '-s', str(smk_path),
            '--cores=all',
            '--keep-going',
            '--use-apptainer',
            '--sdm=apptainer',
            '--apptainer-args', '-B /home/ddeemer -B /depot/lindems/data/Databases/',
            f'--jobs={max_jobs}',
            '--latency-wait=60'
        ]
        if mode != 'dev':
            core_command.append('--executor=slurm')

        # Add default SLURM resources from compute config
        if mode != 'dev' and compute_config:
            default_resources = ['--default-resources']

            # Required: account
            account = compute_config.get('account', '').strip()
            if account:
                default_resources.append(f'slurm_account={account}')

            # Optional: partition
            partition = compute_config.get('partition', '').strip()
            if partition:
                default_resources.append(f'slurm_partition={partition}')

            # Optional: default runtime and memory
            if 'default_runtime' in compute_config:
                default_resources.append(f'runtime={compute_config["default_runtime"]}')

            if 'default_mem_mb' in compute_config:
                default_resources.append(f'mem_mb={compute_config["default_mem_mb"]}')

            # Only add if we have at least the account
            if len(default_resources) > 1:
                core_command.extend(default_resources)

        # Add config parameters to pass to snakemake
        if config_dict:
            config_pairs = [f'{k}={v}' for k, v in config_dict.items()]
            core_command.append('--config')
            core_command.extend(config_pairs)

        return core_command

    @staticmethod
    def _parse_snakemake_output(stderr: str) -> dict:
        '''Best-effort parse of snakemake stderr for structured reporting.'''
        result = {'total': 0, 'completed': 0, 'failed': 0, 'failed_rules': []}

        # Extract "X of Y steps (Z%) done"
        steps_match = re.search(r'(\d+) of (\d+) steps \(\d+%\) done', stderr)
        if steps_match:
            result['completed'] = int(steps_match.group(1))
            result['total'] = int(steps_match.group(2))

        # Extract failed rule names from "Error in rule <name>:"
        failed_rules = re.findall(r'Error in rule (\w+):', stderr)
        result['failed_rules'] = failed_rules
        result['failed'] = len(failed_rules)

        # If we found failed rules but no total, estimate total from completed + failed
        if result['failed'] and not result['total']:
            result['total'] = result['completed'] + result['failed']

        return result

    def _run_subprocess(self, wf_command):
        '''Wrapper for subprocess.run(). Returns CompletedProcess on any exit
        code (even non-zero), or None on launch failure (e.g. snakemake not installed).'''
        LOGGER.debug('Received command and running: %s', wf_command)

        # Pin snakemake's working directory to output_dir so that .snakemake/
        # and any relative rule paths resolve there, regardless of the SSH
        # session's CWD on the cluster.
        output_dir = self.conf.get('output_dir', '')
        cwd = output_dir or None
        if cwd:
            Path(cwd).mkdir(parents=True, exist_ok=True)

        try:
            proc = subprocess.Popen(
                wf_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=cwd,
            )

            # Collect stderr on a background thread so it doesn't block stdout reads.
            stderr_lines: list[str] = []

            def _read_stderr():
                for line in proc.stderr:
                    line = line.rstrip()
                    LOGGER.info('[snakemake] %s', line)
                    stderr_lines.append(line)

            stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
            stderr_thread.start()

            stdout_lines: list[str] = []
            for line in proc.stdout:
                line = line.rstrip()
                LOGGER.info('[snakemake] %s', line)
                stdout_lines.append(line)

            stderr_thread.join()
            proc.wait()

            return subprocess.CompletedProcess(
                args=wf_command,
                returncode=proc.returncode,
                stdout='\n'.join(stdout_lines),
                stderr='\n'.join(stderr_lines),
            )
        except Exception as e:
            LOGGER.error('Failed to launch subprocess %s: %s', wf_command[0], e)
            self.failed(f'Failed to launch subprocess: {e}')
            return None

    def _build_result(self, key_name, proc):
        '''Build a structured result dict from a completed snakemake process.'''
        rules_summary = self._parse_snakemake_output(proc.stderr)
        return {
            'workflow': key_name,
            'returncode': proc.returncode,
            'rules_summary': rules_summary,
            'stdout_tail': proc.stdout[-2000:] if proc.stdout else '',
            'stderr_tail': proc.stderr[-2000:] if proc.stderr else '',
        }

    def _output_prefix(self) -> str:
        """Return the filesystem prefix to prepend to all output paths for this run.

        Reads ``output_dir`` from the caragols config (set via CLI arg or passed
        from the API). If present, returns ``'{output_dir}/'``; otherwise returns
        ``''`` so that output paths remain relative to the SSH working directory.

        Every ``do_*`` workflow method should call this instead of reading
        ``output_dir`` directly, so the logic stays in one place.
        """
        output_dir = self.conf.get('output_dir', '')
        return f"{output_dir.rstrip('/')}/" if output_dir else ''

    def _run_pipeline(self, key_name: str, smk_config: dict, cache_map: dict = None, mode='dev', compute_config: dict = None):
        '''Shared pipeline execution: cache containers, restore outputs, run snakemake, store outputs.'''
        run_id = str(uuid.uuid4())
        LOGGER.info('Finished installing bioinformatics-tools repository')
        LOGGER.info('Starting workflow "%s" run_id=%s', key_name, run_id)

        selected_wf = WORKFLOWS.get(key_name)
        if not selected_wf:
            self.failed(f'No workflow key found for "{key_name}"')
            return 1

        # Download / ensure .sif files are cached (skip if none needed, e.g. selftest)
        if selected_wf.sif_files:
            try:
                cache_sif_files(selected_wf.sif_files)
            except CacheSifError as e:
                LOGGER.critical('Error with cache_sif_files: %s', e)
                self.failed(f'Error with cache_sif_files: {e}')
                return 1

        # Restore cached outputs from DB so snakemake skips completed rules
        db_path = smk_config.get('main_database')
        input_file = smk_config.get('input_fasta') or smk_config.get('input_file')
        restored = {}
        if cache_map and db_path and input_file:
            restored = restore_all(db_path, input_file, cache_map)
            LOGGER.info('Cache restore results: %s', restored)

        # Build and run snakemake
        wf_command = self.build_executable(selected_wf, config_dict=smk_config, mode=mode, compute_config=compute_config)
        LOGGER.info('Running snakemake command: %s', ' '.join(wf_command))
        proc = self._run_subprocess(wf_command)

        # Launch failure (e.g. snakemake not installed) — already called self.failed()
        if proc is None:
            return 1

        result = self._build_result(key_name, proc)

        if proc.returncode != 0:
            LOGGER.error('Snakemake failed (rc=%d): %s', proc.returncode, result['rules_summary'])
            if cache_map and db_path and input_file:
                log_workflow_run(db_path, run_id, input_file, key_name,
                                 result['rules_summary'].get('completed', 0), status='failed')
            self.failed(msg=f'Workflow "{key_name}" failed', dex=result)
            return proc.returncode

        # Success — store outputs and log the run
        if cache_map and db_path and input_file:
            # Only store outputs that were cache misses (newly computed)
            tools_to_store = {tool: paths for tool, paths in cache_map.items()
                            if not restored.get(tool, False)}
            if tools_to_store:
                store_all(db_path, input_file, tools_to_store)
            else:
                LOGGER.info('All outputs were cache hits — skipping redundant storage')
            log_workflow_run(db_path, run_id, input_file, key_name,
                             result['rules_summary'].get('completed', 0), status='success')

        self.succeeded(msg=f'Workflow "{key_name}" completed successfully', dex=result)

    @command
    def do_example(self):
        '''example workflow to execute'''
        input_file = self.conf.get('input')
        if not input_file:
            LOGGER.error('No input file specified. Use: dane_wf example input: <file>')
            self.failed('No input file specified')
            return 1

        input_path = Path(input_file)
        prodigal_config = self.conf.get('prodigal', {})

        smk_config = {
            'input_fasta': input_file,
            'output_fasta': f"{input_path.stem}-output.txt",
            'prodigal_threads': prodigal_config.get('threads', 4),
        }

        self._run_pipeline('example', smk_config)

    def _selftest_config(self, stem, tmpdir, inject_failure=False):
        '''Build smk_config and cache_map for selftest workflows.'''
        td = Path(tmpdir)
        out_step_a = str(td / f"step_a/{stem}-step_a.out")
        out_step_a_extra = str(td / f"step_a/{stem}-step_a.extra")
        out_step_a_db = str(td / f"step_a/{stem}-step_a_db.tkn")
        out_step_b = str(td / f"step_b/{stem}-step_b.out")
        out_step_b_db = str(td / f"step_b/{stem}-step_b_db.tkn")
        out_step_c_primary = str(td / f"step_c/{stem}-step_c.tsv")
        out_step_c_secondary = str(td / f"step_c/{stem}-step_c_count.tsv")
        out_step_c_db = str(td / f"step_c/{stem}-step_c_db.tkn")

        # For selftest, use temp DB path (not required from config)
        selftest_db = str(td / 'selftest.db')

        smk_config = {
            'workdir': tmpdir,
            'stem': stem,
            'inject_failure': str(inject_failure).lower(),
            'out_step_a': out_step_a,
            'out_step_a_extra': out_step_a_extra,
            'out_step_a_db': out_step_a_db,
            'out_step_b': out_step_b,
            'out_step_b_db': out_step_b_db,
            'out_step_c_primary': out_step_c_primary,
            'out_step_c_secondary': out_step_c_secondary,
            'out_step_c_db': out_step_c_db,
            'main_database': selftest_db,
        }

        cache_map = {
            'step_a': [out_step_a, out_step_a_extra],
            'step_a_db': [out_step_a_db],
            'step_b': [out_step_b],
            'step_b_db': [out_step_b_db],
            'step_c': [out_step_c_primary, out_step_c_secondary],
            'step_c_db': [out_step_c_db],
        }

        return smk_config, cache_map

    @command
    def do_quick_example(self, inject_failure=False):
        '''Run selftest with real margie.db cache (deterministic input — cached on second run).'''
        stem = 'quick-example'

        with tempfile.TemporaryDirectory(prefix='dane_quick_') as tmpdir:
            # Deterministic content so the hash is stable across runs.
            # First run: cache miss → snakemake runs → store_all caches.
            # Second run: cache hit → restore_all writes files → snakemake skips.
            tmp_input = str(Path(tmpdir) / f'{stem}.txt')
            Path(tmp_input).write_text('quick-example deterministic input\n')

            smk_config, cache_map = self._selftest_config(stem, tmpdir, inject_failure)
            smk_config['input_file'] = tmp_input

            self._run_pipeline('selftest', smk_config, cache_map, mode='dev')

    @command
    def do_fresh_test(self, inject_failure=False):
        '''Run selftest with real margie.db — unique input each run so cache always misses.'''
        stem = 'fresh-test'

        with tempfile.TemporaryDirectory(prefix='dane_freshtest_') as tmpdir:
            # Unique content per run (includes timestamp) so the hash is always new.
            # restore_all will miss → snakemake runs all rules → store_all caches.
            tmp_input = str(Path(tmpdir) / f'{stem}.txt')
            Path(tmp_input).write_text(f'fresh-test {self.timestamp}\n')

            smk_config, cache_map = self._selftest_config(stem, tmpdir, inject_failure)
            smk_config['input_file'] = tmp_input

            self._run_pipeline('selftest', smk_config, cache_map, mode='dev')

    @command
    def do_margie(self, mode='slurm'):
        '''run margie workflow'''
        input_file = self.conf.get('input')
        if not input_file:
            LOGGER.error('No input file specified. Use: dane_wf margie input: <file>')
            self.failed('No input file specified')
            return 1

        # Require main_database from config - no fallback
        main_database = self.conf.get('main_database', None)
        if not main_database:
            LOGGER.error('main_database not set in config. Add main_database: <path> to your ~/.config/bioinformatics-tools/config.yaml')
            self.failed('main_database configuration is required')
            return 1

        # Expand ~ in database path (SQLite doesn't understand ~)
        main_database = str(Path(main_database).expanduser())

        # Extract and validate compute config for SLURM mode
        compute_config = None
        if mode != 'dev':
            compute_config = self.conf.get('compute', {}).get('cluster-default', {})
            slurm_account = compute_config.get('account', '').strip()
            if not slurm_account:
                LOGGER.error('compute.cluster-default.account not set in config. Add account: <your-slurm-account> to your ~/.config/bioinformatics-tools/config.yaml')
                self.failed('SLURM account configuration is required for cluster execution')
                return 1

        stem = Path(input_file).stem
        prefix = self._output_prefix()

        # Output paths
        out_prodigal = f"{prefix}prodigal/{stem}-prodigal.tkn"
        out_prodigal_faa = f"{prefix}prodigal/{stem}-prodigal.faa"
        out_prodigal_db = f"{prefix}prodigal/{stem}-prodigal_db.tkn"
        out_pfam = f"{prefix}pfam/{stem}-pfam.tkn"
        out_pfam_db = f"{prefix}pfam/{stem}-pfam_db.tkn"
        out_cog = f"{prefix}cog/{stem}-cog.tkn"
        out_cog_classify = f"{prefix}cog/cog_classify.tsv"
        out_cog_count = f"{prefix}cog/cog_count.tsv"
        out_cog_db = f"{prefix}cog/{stem}-cog_db.tkn"
        cog_outdir = f"{prefix}cog"
        out_kofam = f"{prefix}kofam/{stem}-kofam.tkn"
        out_kofam_db = f"{prefix}kofam/{stem}-kofam_db.tkn"

        smk_config = {
            'input_fasta': input_file,
            'out_prodigal': out_prodigal,
            'out_prodigal_faa': out_prodigal_faa,
            'out_prodigal_db': out_prodigal_db,
            'out_pfam': out_pfam,
            'out_pfam_db': out_pfam_db,
            'out_cog': out_cog,
            'out_cog_classify': out_cog_classify,
            'out_cog_count': out_cog_count,
            'out_cog_db': out_cog_db,
            'cog_outdir': cog_outdir,
            # 'out_dbcan': f"{stem}-dbcan.tkn",
            'out_kofam': out_kofam,
            'out_kofam_db': out_kofam_db,
            'main_database': main_database,
            # Hierarchical tool configs - pass entire sections to snakemake
            'prodigal': self.conf.get('prodigal', {}),
            'pfam': self.conf.get('pfam', {}),
            'cog': self.conf.get('cog', {}),
            'dbcan': self.conf.get('dbcan', {}),
            'kofam': self.conf.get('kofam', {}),
        }

        cache_map = {
            'prodigal': [out_prodigal, out_prodigal_faa],
            'prodigal_db': [out_prodigal_db],
            'pfam': [out_pfam],
            'pfam_db': [out_pfam_db],
            'cog': [out_cog, out_cog_classify, out_cog_count],
            'cog_db': [out_cog_db],
            'kofam': [out_kofam],
            'kofam_db': [out_kofam_db],
        }

        self._run_pipeline('margie', smk_config, cache_map, mode=mode, compute_config=compute_config)
