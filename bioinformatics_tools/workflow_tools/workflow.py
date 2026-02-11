'''
Workflow tools generate
Invoked: $ dane_wf wf: example <params/options/io>
'''
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from bioinformatics_tools.caragols import clix
from bioinformatics_tools.caragols.condo import CxNode
from bioinformatics_tools.file_classes.base_classes import command
from bioinformatics_tools.utilities import ssh_slurm
from bioinformatics_tools.workflow_tools.bapptainer import (
    CacheSifError, cache_sif_files, get_verified_sif_file,
    run_apptainer_container)
from bioinformatics_tools.workflow_tools.models import (ApptainerKey,
                                                        WorkflowKey)
from bioinformatics_tools.workflow_tools.output_cache import restore_all, store_all

LOGGER = logging.getLogger(__name__)
WORKFLOW_DIR = Path(__file__).parent


apptainer_keys: dict[str, ApptainerKey] = {
    'prodigal': ApptainerKey(
        executable='apptainer.lima',
        sif_path='prodigal.sif',
        commands=[]
        )
}

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


class WorkflowBase(clix.App):
    '''Base class for all workflows. Allows us to have access to config, logging, and reporting
    '''
    
    def __init__(self, workflow_id=None):
        LOGGER.debug('Starting __init__ of WorkflowBase')
        self.workflow_id = workflow_id
        self.timestamp = datetime.now().strftime("%d%m%y-%H%M")

        LOGGER.debug('Using the workflow id of %s', self.workflow_id)

        super().__init__()
    
    def build_snakemake_command(self) -> list[str]:
        pass
    
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
    
    def _run_workflow(self, wf_command):
        '''essentially a wrapper for subprocess.run() to tightly control snakemake execution'''
        LOGGER.debug('Received command and running: %s', wf_command)
        try:
            subprocess.run(wf_command, check=True)
        except Exception as e:
            LOGGER.error('Critical ERROR during subprocess.run(%s): %s', wf_command, e)
            self.failed(f'Critical ERROR during subprocess.run({wf_command}): {e}')
        return 0
    
    def _run_workflow_ssh(self, cmd, credentials=False):
        '''connect to ssh and execute the workflow instead of locally
        this would be using paramiko's ssh client instead of subprocess.run
        '''
        result = ssh_slurm.submit_ssh_job(cmd)
        return result

    
    @command
    def do_example(self, ssh=False):
        '''example workflow to execute
        This shouldn not need to worry about SSH at all'''
        #TODO: Return a report object? Or just 0 vs. 1, or None?

        LOGGER.info('Config:\n%s', self.conf.show())

        # ----------------------- Step 0 - Get the WorkflowKey ----------------------- #
        if not (selected_wf := workflow_keys.get('example')):
            return 1

        # -------------- Step 1 - Get the input file (eventually files) -------------- #
        input_file = self.conf.get('input')
        if not input_file:
            LOGGER.error('No input file specified. Use: dane_wf example input: <file>')
            self.failed('No input file specified')
            return 1

        # ------- Step 2 - Get the appropriate output file from the input file ------- #
        # Derive output filename from input (e.g., file.fasta -> file-output.txt)
        # Basically we need a way to trace input to final output
        input_path = Path(input_file)
        output_file = f"{input_path.stem}-output.txt"
        LOGGER.info('Input file: %s', input_file)
        LOGGER.info('Output file: %s', output_file)

        # Log which snakemake executable will be used
        try:
            which_result = subprocess.run(['which', 'snakemake'], capture_output=True, text=True, check=True)
            LOGGER.info('Using snakemake from: %s', which_result.stdout.strip())
        except subprocess.CalledProcessError:
            LOGGER.warning('Could not find snakemake executable in PATH')

        # --- Step 3 - get program-specific params and send to snakemake as config --- #
        prodigal_config = self.conf.get('prodigal')
        threads = prodigal_config.get('threads')
        #TODO: Is there a way to automatically get all config from prodigal
        # or do we want to control this here?
        smk_config = {
            'input_fasta': input_file,
            'output_fasta': output_file,
            'prodigal_threads': threads
        }

        # Target the final output to chain rules together
        # May only need the final target?
        final_target = "results/done.txt"

        # -------- TODO: Step 3.5 - Download / ensure .sif file is downloaded -------- #
        # ~/.cache/bioinformatics-tools/prodigal.sif --> multiple for some snakemake pipelines
        get_verified_sif_file(selected_wf.sif_files)

        # ----------------------- Step 4 - build the executable ---------------------- #
        wf_command = self.build_executable(selected_wf, config_dict=smk_config)
        # wf_command = self.build_snakemake_command(selected_wf, default_output)
        LOGGER.info('Running snakemake command: %s', wf_command)
        str_smk = ' '.join(wf_command)
        LOGGER.info('String snakemake: %s', str_smk)
        print(f'\n=== SNAKEMAKE COMMAND ===\n{str_smk}\n========================\n')

        # ------ Step 5 Execute the actual workflow (happens within our UV env) ------ #
        if not ssh:  #TODO SSH compatibility
            self._run_workflow(wf_command)
            self.succeeded(msg="All good in the neighborhood (AppleBees TM)")
        # else:
            # self._run_workflow_ssh(str_smk)
            # self.succeeded(msg="Ran on remote cluster all good.")

        #TODO: Option to run via subprocess locally vs. SSH login node vs. SSH+Slurm
    

    def get_prg_args(self, config_group):
        '''find relevant configuration settings to add to container run
        '''
        args_list = []

        # Get the config node for this program
        try:
            prog_node: CxNode = self.conf.get(config_group)
        except KeyError:
            LOGGER.warning('No configuration found for %s', config_group)
            return args_list

        # If it's not a CxNode (e.g., it's a simple value), return empty
        if not hasattr(prog_node, 'children'):
            LOGGER.warning('%s is not a configuration group', config_group)
            return args_list

        # Iterate over the direct children of this config group
        for key, value in prog_node.children.items():
            # Skip nested CxNode objects (only process direct key-value pairs)
            if not isinstance(value, type(prog_node)):
                # Convert key to command-line flag format
                flag = f'--{key}'
                # Convert value to string
                str_value = str(value)
                # Add to args list
                args_list.extend([flag, str_value])

        LOGGER.debug('Generated args for %s: %s', config_group, args_list)
        return args_list

    @command
    def do_prodigal(self):
        '''run prodigal''' 
        EXECUTABLE = 'prodigal'

        if not (container := apptainer_keys.get('prodigal')):
            self.failed('No known match for "prodigal"')
            return
        # wf_command = self.build_snakemake_command(selected_wf, default_output)
        # self._run_workflow(wf_command)
        prg_args = self.get_prg_args(config_group='prodigal')
        prg_args.insert(0, EXECUTABLE)
        LOGGER.info('Program arguments: %s', prg_args)
        exit_code = run_apptainer_container(container, prg_args)
        self.succeeded(msg='Successfully ran prodigal!')
    
    @command
    def do_margie(self, ssh=False, mode='dev'):
        '''example workflow to execute
        This shouldn not need to worry about SSH at all'''
        #TODO: Return a report object? Or just 0 vs. 1, or None?

        LOGGER.info('Config:\n%s', self.conf.show())

        # ----------------------- Step 0 - Get the WorkflowKey ----------------------- #
        if not (selected_wf := workflow_keys.get('margie')):
            return 1

        # -------------- Step 1 - Get the input file (eventually files) -------------- #
        input_file = self.conf.get('input')
        if not input_file:
            LOGGER.error('No input file specified. Use: dane_wf example input: <file>')
            self.failed('No input file specified')
            return 1

        # ------- Step 2 - Get the appropriate output file from the input file ------- #
        # Derive output filename from input (e.g., file.fasta -> file-output.txt)
        # Basically we need a way to trace input to final output
        input_path = Path(input_file)
        out_prodigal = f"prodigal/{input_path.stem}-prodigal.tkn"
        out_prodigal_faa = f"prodigal/{input_path.stem}-prodigal.faa"
        out_prodigal_db = f"prodigal/{input_path.stem}-prodigal_db.tkn"
        out_pfam = f"pfam/{input_path.stem}-pfam.tkn"
        out_pfam_db = f"pfam/{input_path.stem}-pfam_db.tkn"
        out_cog_classify = "cog/cog_classify.tsv"
        out_cog_count = "cog/cog_count.tsv"
        out_cog_db = f"cog/{input_path.stem}-cog_db.tkn"
        out_dbcan = f"{input_path.stem}-dbcan.tkn"  # Not being used not
        out_kofam = f"{input_path.stem}-kofam.tkn"  # Not being used not
        LOGGER.info('Input file: %s', input_file)
        LOGGER.info('out_prodigal file: %s', out_prodigal)
        LOGGER.info('out_dbcan file: %s', out_dbcan)

        # Log which snakemake executable will be used
        try:
            which_result = subprocess.run(['which', 'snakemake'], capture_output=True, text=True, check=True)
            LOGGER.info('Using snakemake from: %s', which_result.stdout.strip())
        except subprocess.CalledProcessError:
            LOGGER.warning('Could not find snakemake executable in PATH')

        # --- Step 3 - get program-specific params and send to snakemake as config --- #
        prodigal_config = self.conf.get('prodigal')
        threads = prodigal_config.get('threads')
        margie_db = self.conf.get('margie_db', '/depot/lindems/data/margie/margie.db')
        #TODO: Is there a way to automatically get all config from prodigal
        # or do we want to control this here?
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
            'out_dbcan': out_dbcan,
            'out_kofam': out_kofam,
            'prodigal_threads': threads,
            'margie_db': margie_db,
        }

        # -------- TODO: Step 3.5 - Download / ensure .sif file is downloaded -------- #
        # ~/.cache/bioinformatics-tools/prodigal.sif --> multiple for some snakemake pipelines
        try:
            cache_sif_files(selected_wf.sif_files)
        except CacheSifError as e:
            LOGGER.critical('Error with cache_sif_files: %s', e)
            self.failed(f'Error with cache_sif_files: {e}')

        # ----------- Step 3.6 - Restore cached outputs from the DB ----------- #
        cache_map = {
            'prodigal': [out_prodigal, out_prodigal_faa],
            'prodigal_db': [out_prodigal_db],
            'pfam': [out_pfam],
            'pfam_db': [out_pfam_db],
            'cog': [out_cog_classify, out_cog_count],
            'cog_db': [out_cog_db],
        }
        restored = restore_all(margie_db, input_file, cache_map)
        LOGGER.info('Cache restore results: %s', restored)

        # ----------------------- Step 4 - build the executable ---------------------- #
        wf_command = self.build_executable(selected_wf, config_dict=smk_config, mode=mode)
        # wf_command = self.build_snakemake_command(selected_wf, default_output)
        LOGGER.info('Running snakemake command: %s', wf_command)
        str_smk = ' '.join(wf_command)
        LOGGER.info('String snakemake: %s', str_smk)
        print(f'\n=== SNAKEMAKE COMMAND ===\n{str_smk}\n========================\n')

        # ------ Step 5 Execute the actual workflow (happens within our UV env) ------ #
        if not ssh:  #TODO SSH compatibility
            self._run_workflow(wf_command)

            # ---- Step 5.5 - Store new outputs into DB cache ---- #
            store_all(margie_db, input_file, cache_map)

            self.succeeded(msg="All good in the neighborhood (AppleBees TM)")
        # else:
            # self._run_workflow_ssh(str_smk)
            # self.succeeded(msg="Ran on remote cluster all good.")

        #TODO: Option to run via subprocess locally vs. SSH login node vs. SSH+Slurm
