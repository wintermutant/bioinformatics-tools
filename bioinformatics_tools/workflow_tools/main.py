'''
Command line entrypoint for workflows
TODO: Need to match the test.smk to the command line dane_wf test, not the type
'''
import importlib
import logging
import os
import sys

from bioinformatics_tools.caragols.logger import config_logging_for_app
from bioinformatics_tools.file_classes.main import match_alias_to_module, find_file_type

LOGGER = logging.getLogger(__name__)  # Creates logger named 'bioinformatics_tools.workflow_tools.main'

snakemake_files = [f.rsplit('.', 1)[0] for f in os.listdir(os.path.dirname(__file__)) if f.endswith('.smk')]
snakemake_files = [x for x in snakemake_files if x not in ['main', 'Binning', 'Annotate', 'Alignment']]

print('Snakemake files: ', snakemake_files)


def cli():
    '''Command line interface for the script.
    '''
    # Step 0 - Configure Logging
    config_logging_for_app()
    startup_info = {
        'cwd': os.getcwd(),
        'user': os.getlogin(),
        'argv': sys.argv,
    }
    LOGGER.info('Starting workflow_tools with info: %s', startup_info)

    # -------------------------- Step 1 - Find the type -------------------------- #
    matched = False
    type_ = find_file_type(sys.argv)
    LOGGER.info('Recognize file type: %s', type_)
    # -------------------- Step 2 - Match the type to a module ------------------- #
    alias_to_module: dict = match_alias_to_module()
    if type_:
        for module_str, type_identifier in alias_to_module.items():
            if type_.lower() in type_identifier:
                matched = True
                LOGGER.info('✅ Recognized type (%s) and matched to module', type_)
                import_string = f"bioinformatics_tools.file_classes.{module_str}"
                LOGGER.info('📦 Importing %s', import_string)
                current_module = importlib.import_module(import_string)
                current_class = None
                for type_id in type_identifier:
                    if getattr(current_module, type_id, None):
                        LOGGER.info('Using alias %s to refer to module %s', type_id, module_str)
                        current_class = getattr(current_module, type_id)
                        break
                if current_class is None:
                    LOGGER.error('Could not find a class in module %s that matches any of the aliases %s', module_str, type_identifier)
                    sys.exit(1)  #TODO: Show a report here
                # Controlling the execution of the class
                data = current_class()  # Shows config
                if not data.valid:
                    LOGGER.info('File provided failed validation test')
                    data.file_not_valid_report()
                # Executing the Class
                data.run()
                # Finishing the Class
            else:
                pass
        if not matched:
            LOGGER.error('Program not found in available programs to deal with file type: %s Exiting...\n\n', type_)
    else:
        if any(arg in sys.argv for arg in ("help", "Help", "HELP")):
            LOGGER.info('🆘 Help requested')
            LOGGER.info('The following file types are recognized and can be specified via the command line\n\033[92mdane type: <file_type>\033[0m')
            help_string = 'Available file types:\n'
            for type_identifier in file_type_identifiers:
                help_string += f'  {type_identifier}\n'
            LOGGER.info(help_string)
        else:
            LOGGER.error('No file type provided. Please specify via the command line\ndane type: <file_type>\nExiting...')


if __name__ == "__main__":
    cli()