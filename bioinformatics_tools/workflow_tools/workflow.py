'''
Workflow tools generate
Invoked: $ dane_wf wf: example <params/options/io>
'''
from dataclasses import dataclass
from datetime import datetime
import logging

from bioinformatics_tools.file_classes.base_classes import ListHandler
from bioinformatics_tools.caragols import clix

LOGGER = logging.getLogger(__name__)


@dataclass
class WorkflowKey:
    '''Information needed to run a workflow and map from cmd line'''
    cmd_identifier: str
    snakemake_file: str
    other: list[str]

workflow_keys: list[WorkflowKey] = [
    WorkflowKey(
    cmd_identifier='example',
    snakemake_file='example.smk',
    other=['']
    ),
    WorkflowKey(
    cmd_identifier='other',
    snakemake_file='example2.smk',
    other=['']
    ),
]


class WorkflowBase(clix.App):
    '''Base class for all workflows. Allows us to have access to config, logging, and reporting
    '''
    
    def __init__(self, workflow_id):
        LOGGER.debug('Starting __init__ of WorkflowBase')
        self.workflow_id = workflow_id
        self.timestamp = datetime.now().strftime("%d%m%y-%H%M")

        LOGGER.debug('Using the workflow id of %s', self.workflow_id)

        super().__init__()
    
    def get_workflow_dobject(self) -> WorkflowKey | None:
        '''Convert wf: example string to WorkflowKey object. Mapping stage'''
        for workflow in workflow_keys:
            if self.workflow_id.lower() == workflow.cmd_identifier:
                LOGGER.info('Found workflow: %s \n\n', workflow)
                return workflow
        return None
    
    def build_snakemake_command(self, key: WorkflowKey) -> str:
        '''Given a workflow data object, with access to config and command line args,
        build out a snakemake command'''
        prefix = f'snakemake -s {key.snakemake_file}'
        apptainer_cmds = '--core 1 --use-apptainer --sdm apptainer'
        output_files = "example-output.txt"  #TODO: This will be inside Workflow data object
        return ' '.join([prefix, output_files, apptainer_cmds])


    def run_workflow(self):
        '''Change this just to run, or have it be compatible with clix.App.run
        to not overload terms'''
        wf_object = self.get_workflow_dobject()
        print('Running workflow with object: %s', wf_object)
        if wf_object:
            wf_command = self.build_snakemake_command(wf_object)
        LOGGER.info('Preparing to run:\n$ %s', wf_command)
        # TODO: Issue here --> when I type fakearg: argu, it doens't show up in self.conf.show
        # TODO: Nor does the stuff from the config file
        LOGGER.info('\nAlso, I have access to allll this good info:\n\n%s', self.conf.show())
        return True