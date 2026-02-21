'''
Single-program execution via Apptainer containers.
Invoked: $ dane_wf prodigal <params/options/io>

For snakemake workflows, see workflow.py.
'''
import logging

from bioinformatics_tools.caragols import clix
from bioinformatics_tools.caragols.condo import CxNode
from bioinformatics_tools.file_classes.base_classes import command
from bioinformatics_tools.workflow_tools.bapptainer import run_apptainer_container
from bioinformatics_tools.workflow_tools.models import ApptainerKey

LOGGER = logging.getLogger(__name__)

apptainer_keys: dict[str, ApptainerKey] = {
    'prodigal': ApptainerKey(
        executable='apptainer.lima',
        sif_path='prodigal.sif',
        commands=[]
    )
}


class ProgramBase(clix.App):
    '''Base class for running single containerized programs.

    Subclassed by WorkflowBase so all @command methods (both single programs
    and snakemake workflows) are available through the same dane_wf entrypoint.
    '''

    def get_prg_args(self, config_group):
        '''Find relevant configuration settings to add to container run.'''
        args_list = []

        try:
            prog_node: CxNode = self.conf.get(config_group)
        except KeyError:
            LOGGER.warning('No configuration found for %s', config_group)
            return args_list

        if not hasattr(prog_node, 'children'):
            LOGGER.warning('%s is not a configuration group', config_group)
            return args_list

        for key, value in prog_node.children.items():
            if not isinstance(value, type(prog_node)):
                args_list.extend([f'--{key}', str(value)])

        LOGGER.debug('Generated args for %s: %s', config_group, args_list)
        return args_list

    @command
    def do_prodigal(self):
        '''run prodigal'''
        EXECUTABLE = 'prodigal'

        if not (container := apptainer_keys.get('prodigal')):
            self.failed('No known match for "prodigal"')
            return

        prg_args = self.get_prg_args(config_group='prodigal')
        prg_args.insert(0, EXECUTABLE)
        LOGGER.info('Program arguments: %s', prg_args)
        run_apptainer_container(container, prg_args)
        self.succeeded(msg='Successfully ran prodigal!')
