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
    
    def __init__(self, workflow_id, detect_mode="medium", run_mode="cli", match=False):
        self.workflow_id = workflow_id
        self.file, self.detect_mode, self.run_mode=run_mode, detect_mode, run_mode

        self.timestamp = datetime.now().strftime("%d%m%y-%H%M")
        self.detect_mode = detect_mode

        # Session log handler - captures logs during this instance's lifetime
        # This is used to log info before the logger is officially setup in clix.App
        # Otherwise, couldn't log stuff before super().__init__() ... #shrug
        self.log_handler = ListHandler()
        self.log_handler.setLevel(logging.INFO)
        # Attach to root bioinformatics_tools logger to capture ALL module logs
        logging.getLogger('bioinformatics_tools').addHandler(self.log_handler)

        LOGGER.debug('Using the workflow id of %s', self.workflow_id)

        if self.run_mode == 'cli':
            super().__init__(file=self.file, run_mode=self.run_mode)
    
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