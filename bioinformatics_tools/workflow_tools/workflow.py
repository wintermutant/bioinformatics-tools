'''
Workflow tools generate
Invoked: $ dane_wf wf: example <params/options/io>
'''
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from bioinformatics_tools.file_classes.base_classes import command
from bioinformatics_tools.workflow_tools.bapptainer import (
    CacheSifError, cache_sif_files)
from bioinformatics_tools.workflow_tools.models import WorkflowKey
from bioinformatics_tools.workflow_tools.output_cache import restore_all, store_all
from bioinformatics_tools.workflow_tools.programs import ProgramBase

LOGGER = logging.getLogger(__name__)
WORKFLOW_DIR = Path(__file__).parent
PROJECT_ROOT = WORKFLOW_DIR.parent.parent
TEST_FILES = PROJECT_ROOT / 'test-files'


workflow_keys: dict[str, WorkflowKey] = {
    'example': WorkflowKey(
    cmd_identifier='example',
    snakemake_file='example.smk',
    other=[''],
    sif_files=[
        ('prodigal.sif', '2.6.3-v1.0'),
        ]
    ),
    'margie': WorkflowKey(
    cmd_identifier='margie',
    snakemake_file='margie.smk',
    other=[''],
    sif_files=[
        ('prodigal.sif', '2.6.3-v1.0'),
        # ('run_dbcan_light', '4.2.0'),
        # ('kofam_scan_light', 'latest'),
        ('pfam_scan_light', 'latest'),
        ('cogclassifier', 'latest')]
    ),
    'selftest': WorkflowKey(
    cmd_identifier='selftest',
    snakemake_file='selftest.smk',
    other=[''],
    sif_files=[],
    ),
}


class WorkflowBase(ProgramBase):
    '''Snakemake workflow execution. Inherits single-program commands from ProgramBase.
    '''
    
    def __init__(self, workflow_id=None):
        LOGGER.debug('Starting __init__ of WorkflowBase')
        self.workflow_id = workflow_id
        self.timestamp = datetime.now().strftime("%d%m%y-%H%M")

        LOGGER.debug('Using the workflow id of %s', self.workflow_id)

        super().__init__()
    
    def build_executable(self, key: WorkflowKey, config_dict: dict = None, mode='notdev') -> list[str]:
        '''Given a workflow data object, with access to config and command line args,
        build out a snakemake command'''
        smk_path = WORKFLOW_DIR / key.snakemake_file
        core_command = [
            'snakemake',
            '-s', str(smk_path),
            '--cores=all',
            '--keep-going',
            '--use-apptainer',
            '--sdm=apptainer',
            '--apptainer-args', '-B /home/ddeemer -B /depot/lindems/data/Databases/',
            '--jobs=5',
            '--latency-wait=60'
        ]
        if mode != 'dev':
            core_command.append('--executor=slurm')

        # Add default SLURM resources (each key=value is a separate arg)
        #TODO: Grab these values from config OR point to Snakemake Profile
        if mode != 'dev':
            core_command.extend([
                '--default-resources',
                'slurm_account=lindems',
                'slurm_partition=cpu',
                'runtime=30',
                'mem_mb=4000'
            ])

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
        try:
            result = subprocess.run(wf_command, capture_output=True, text=True)
            LOGGER.info('snakemake stdout:\n%s', result.stdout)
            if result.stderr:
                LOGGER.info('snakemake stderr:\n%s', result.stderr)
            return result
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

    def _run_pipeline(self, key_name: str, smk_config: dict, cache_map: dict = None, mode='dev'):
        '''Shared pipeline execution: cache containers, restore outputs, run snakemake, store outputs.'''
        selected_wf = workflow_keys.get(key_name)
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
        db_path = smk_config.get('margie_db')
        input_file = smk_config.get('input_fasta') or smk_config.get('input_file')
        if cache_map and db_path and input_file:
            restored = restore_all(db_path, input_file, cache_map)
            LOGGER.info('Cache restore results: %s', restored)

        # Build and run snakemake
        wf_command = self.build_executable(selected_wf, config_dict=smk_config, mode=mode)
        LOGGER.info('Running snakemake command: %s', ' '.join(wf_command))
        proc = self._run_subprocess(wf_command)

        # Launch failure (e.g. snakemake not installed) — already called self.failed()
        if proc is None:
            return 1

        result = self._build_result(key_name, proc)

        if proc.returncode != 0:
            LOGGER.error('Snakemake failed (rc=%d): %s', proc.returncode, result['rules_summary'])
            self.failed(msg=f'Workflow "{key_name}" failed', dex=result)
            return proc.returncode

        # Success — store outputs and report
        if cache_map and db_path and input_file:
            store_all(db_path, input_file, cache_map)

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
        prodigal_config = self.conf.get('prodigal')

        smk_config = {
            'input_fasta': input_file,
            'output_fasta': f"{input_path.stem}-output.txt",
            'prodigal_threads': prodigal_config.get('threads'),
        }

        self._run_pipeline('example', smk_config)

    @command
    def do_quick_example(self, inject_failure=False):
        '''Run the selftest workflow with DB cache restore/store (mirrors margie pipeline).'''
        input_source = TEST_FILES / 'sample-a.txt'
        db_source = TEST_FILES / 'sample.db'
        stem = 'sample-a'

        with tempfile.TemporaryDirectory(prefix='dane_quick_') as tmpdir:
            # Copy the committed DB so store_all doesn't modify the fixture
            db_path = str(Path(tmpdir) / 'sample.db')
            shutil.copy2(str(db_source), db_path)

            # Copy input into tmpdir so snakemake can find it
            tmp_input = str(Path(tmpdir) / 'sample-a.txt')
            shutil.copy2(str(input_source), tmp_input)

            # Output paths (relative to workdir)
            out_step_a = f"step_a/{stem}-step_a.out"
            out_step_a_extra = f"step_a/{stem}-step_a.extra"
            out_step_a_db = f"step_a/{stem}-step_a_db.tkn"
            out_step_b = f"step_b/{stem}-step_b.out"
            out_step_b_db = f"step_b/{stem}-step_b_db.tkn"
            out_step_c_primary = f"step_c/{stem}-step_c.tsv"
            out_step_c_secondary = f"step_c/{stem}-step_c_count.tsv"
            out_step_c_db = f"step_c/{stem}-step_c_db.tkn"

            smk_config = {
                'workdir': tmpdir,
                'input_file': tmp_input,
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
                'margie_db': db_path,
            }

            cache_map = {
                'step_a': [out_step_a, out_step_a_extra],
                'step_a_db': [out_step_a_db],
                'step_b': [out_step_b],
                'step_b_db': [out_step_b_db],
                'step_c': [out_step_c_primary, out_step_c_secondary],
                'step_c_db': [out_step_c_db],
            }

            self._run_pipeline('selftest', smk_config, cache_map, mode='dev')

    @command
    def do_fresh_test(self, inject_failure=False):
        '''Run the selftest workflow without cache (snakemake runs all touch rules from scratch).'''
        stem = 'sample-a'

        with tempfile.TemporaryDirectory(prefix='dane_freshtest_') as tmpdir:
            # Create a dummy input file in the temp dir
            tmp_input = str(Path(tmpdir) / 'sample-a.txt')
            Path(tmp_input).write_text('sample input for fresh test\n')

            smk_config = {
                'workdir': tmpdir,
                'input_file': tmp_input,
                'stem': stem,
                'inject_failure': str(inject_failure).lower(),
            }

            self._run_pipeline('selftest', smk_config, mode='dev')

    @command
    def do_margie(self, mode='dev'):
        '''run margie workflow'''
        input_file = self.conf.get('input')
        if not input_file:
            LOGGER.error('No input file specified. Use: dane_wf margie input: <file>')
            self.failed('No input file specified')
            return 1

        stem = Path(input_file).stem
        prodigal_config = self.conf.get('prodigal')
        margie_db = self.conf.get('margie_db', '/depot/lindems/data/margie/margie.db')

        # Output paths
        out_prodigal = f"prodigal/{stem}-prodigal.tkn"
        out_prodigal_faa = f"prodigal/{stem}-prodigal.faa"
        out_prodigal_db = f"prodigal/{stem}-prodigal_db.tkn"
        out_pfam = f"pfam/{stem}-pfam.tkn"
        out_pfam_db = f"pfam/{stem}-pfam_db.tkn"
        out_cog_classify = "cog/cog_classify.tsv"
        out_cog_count = "cog/cog_count.tsv"
        out_cog_db = f"cog/{stem}-cog_db.tkn"

        smk_config = {
            'input_fasta': input_file,
            'out_prodigal': out_prodigal,
            'out_prodigal_faa': out_prodigal_faa,
            'out_prodigal_db': out_prodigal_db,
            'out_pfam': out_pfam,
            'out_pfam_db': out_pfam_db,
            'out_cog_classify': out_cog_classify,
            'out_cog_count': out_cog_count,
            'out_cog_db': out_cog_db,
            'out_dbcan': f"{stem}-dbcan.tkn",
            'out_kofam': f"{stem}-kofam.tkn",
            'prodigal_threads': prodigal_config.get('threads'),
            'margie_db': margie_db,
        }

        cache_map = {
            'prodigal': [out_prodigal, out_prodigal_faa],
            'prodigal_db': [out_prodigal_db],
            'pfam': [out_pfam],
            'pfam_db': [out_pfam_db],
            'cog': [out_cog_classify, out_cog_count],
            'cog_db': [out_cog_db],
        }

        self._run_pipeline('margie', smk_config, cache_map, mode=mode)
