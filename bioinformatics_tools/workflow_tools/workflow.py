'''
Workflow tools generate
Invoked: $ dane_wf wf: example <params/options/io>
'''
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
import subprocess

from bioinformatics_tools.file_classes.base_classes import command
from bioinformatics_tools.workflow_tools.bapptainer import run_apptainer_container
from bioinformatics_tools.workflow_tools.models import ApptainerKey, WorkflowKey
from bioinformatics_tools.caragols import clix
from bioinformatics_tools.caragols.condo import CxNode

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
    other=['']
    ),
    'other': WorkflowKey(
    cmd_identifier='other',
    snakemake_file='example2.smk',
    other=['']
    ),
    'prodigal': WorkflowKey(
        cmd_identifier='prodigal',
        snakemake_file='prodigal.sif',
        other=[]
    )
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
    
    def get_workflow_dobject (self) -> WorkflowKey | None:
        '''mapper something to a workflow object. Ideal to be lenient and multi-source'''
        return None
    
    def build_snakemake_command(self) -> list[str]:
        pass
    
    def build_executable(self, key: WorkflowKey, output: str | list[str]) -> list[str]:
        '''Given a workflow data object, with access to config and command line args,
        build out a snakemake command'''
        smk_path = WORKFLOW_DIR / key.snakemake_file  #Change this location if we want to expand snakemake locations
        output_list = [output] if isinstance(output, str) else output
        core_command = [
            'snakemake',
            '-s', str(smk_path),
            '--core=1',
            '--use-apptainer',
            '--sdm=apptainer',
        ]
        core_command.extend(output_list)
        return core_command
    
    def _run_workflow(self, wf_command):
        '''essentially a wrapper for subprocess.run() to tightly control snakemake execution'''
        try:
            subprocess.run(wf_command, check=True)
        except Exception as e:
            LOGGER.error('Critical ERROR during subprocess.run(%s): %s', wf_command, e)
            self.failed(f'Critical ERROR during subprocess.run({wf_command}): {e}')
        return 0
    
    @command
    def do_example(self):
        '''example workflow to execute'''
        #TODO: Return a report object? Or just 0 vs. 1, or None?

        default_output = 'example-output.txt'

        if not (selected_wf := workflow_keys.get('example')):
            return 1
        wf_command = self.build_snakemake_command(selected_wf, default_output)
        LOGGER.debug('Running snakemake command: %s', wf_command)
        str_smk = ' '.join(wf_command)
        LOGGER.debug('String snakemake: %s', str_smk)
        self._run_workflow(wf_command)
        self.succeeded(msg="All good in the neighborhood (AppleBees TM)")
    

    def get_prg_args(self, config_group):
        '''find relevant configuration settings to add to container run

        Args:
            config_group: The top-level config key (e.g., 'prodigal')

        Returns:
            List of command-line arguments in format ['--key', 'value', ...]
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
    def do_other(self):
        '''second workflow to execute'''
        default_output = 'delete.me'

        if not (selected_wf := workflow_keys.get('other')):
            self.failed('Parsed command line to "do_other", but did not match selected_wf')
            return
            
        wf_command = self.build_snakemake_command(selected_wf, default_output)
        self._run_workflow(wf_command)
        self.succeeded(msg='Did the other workflow!')
        
