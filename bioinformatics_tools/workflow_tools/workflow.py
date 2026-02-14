'''
Workflow tools generate
Invoked: $ dane_wf wf: example <params/options/io>
'''
import logging
import subprocess
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
        ('run_dbcan_light', '4.2.0'),
        ('kofam_scan_light', 'latest'),
        ('pfam_scan_light', 'latest'),
        ('cogclassifier', 'latest')]
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
        smk_path = WORKFLOW_DIR / key.snakemake_file  #Change this location if we want to expand snakemake locations
        # output_list = [output] if isinstance(output, str) else output
        core_command = [
            'snakemake',
            '-s', str(smk_path),
            # '-np',
            '--cores=all',
            '--use-apptainer',
            '--sdm=apptainer',
            '--apptainer-args', '-B /home/ddeemer -B /depot/lindems/data/Databases/',
            '--executor=slurm',
            # '--workflow-profile=/home/ddeemer/.config/bioinformatics-tools/default-smk.yaml'
            '--jobs=5',
            '--latency-wait=60'
        ]
        if mode != 'dev':
            core_command.append('--executor=slurm')

        # Add default SLURM resources (each key=value is a separate arg)
        #TODO: Grab these values from config OR point to Snakemake Profile
        core_command.extend([
            '--default-resources',
            'slurm_account=lindems',
            'slurm_partition=cpu',
            'runtime=30',
            'mem_mb=4000'
        ])

        # Add config parameters to pass to snakemake
        # Build all config as a single --config argument to avoid parsing issues
        if config_dict:
            config_pairs = [f'{k}={v}' for k, v in config_dict.items()]
            core_command.append('--config')
            core_command.extend(config_pairs)

        # core_command.extend(output_list)
        return core_command
    
    def _run_subprocess(self, wf_command):
        '''essentially a wrapper for subprocess.run() to tightly control snakemake execution'''
        LOGGER.debug('Received command and running: %s', wf_command)
        try:
            subprocess.run(wf_command, check=True)
        except Exception as e:
            LOGGER.error('Critical ERROR during subprocess.run(%s): %s', wf_command, e)
            self.failed(f'Critical ERROR during subprocess.run({wf_command}): {e}')
        return 0

    def _run_pipeline(self, key_name: str, smk_config: dict, cache_map: dict = None, mode='dev'):
        '''Shared pipeline execution: cache containers, restore outputs, run snakemake, store outputs.'''
        selected_wf = workflow_keys.get(key_name)
        if not selected_wf:
            self.failed(f'No workflow key found for "{key_name}"')
            return 1

        # Download / ensure .sif files are cached
        try:
            cache_sif_files(selected_wf.sif_files)
        except CacheSifError as e:
            LOGGER.critical('Error with cache_sif_files: %s', e)
            self.failed(f'Error with cache_sif_files: {e}')
            return 1

        # Restore cached outputs from DB so snakemake skips completed rules
        db_path = smk_config.get('margie_db')
        input_file = smk_config.get('input_fasta')
        if cache_map and db_path and input_file:
            restored = restore_all(db_path, input_file, cache_map)
            LOGGER.info('Cache restore results: %s', restored)

        # Build and run snakemake
        wf_command = self.build_executable(selected_wf, config_dict=smk_config, mode=mode)
        LOGGER.info('Running snakemake command: %s', ' '.join(wf_command))
        self._run_subprocess(wf_command)

        # Store new outputs into DB cache
        if cache_map and db_path and input_file:
            store_all(db_path, input_file, cache_map)

        self.succeeded(msg=f'Workflow "{key_name}" completed successfully')

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
