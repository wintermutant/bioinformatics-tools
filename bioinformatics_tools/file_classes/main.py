'''
This is an exploratory script that takes in an input file and determines
which snakemake rules can be ran on it. Ideally it'd be able to parse a
library of snakemake files and provide some natural-language descriptions
of what the process looks like.

The natural language description of the pipeline would be hard-coded
since we know what input and output to expect.
'''
import importlib
import logging
import os
import sys

from bioinformatics_tools.caragols.logger import config_logging_for_app

LOGGER = logging.getLogger(__name__)

package_spec = importlib.util.find_spec("bioinformatics_tools.file_classes")
package_path = package_spec.submodule_search_locations[0]

real_py_class_filenames = [f.rsplit('.', 1)[0] for f in os.listdir(package_path) if f.endswith('.py') and not f.startswith('__')]
# real_py_class_filenames = [x for x in real_py_class_filenames if x not in ['main', 'BaseClasses']]
real_py_class_filenames = [x for x in real_py_class_filenames if x == 'Fasta']
file_type_identifiers = [f for f in real_py_class_filenames]  # TODO: Is this needed?


def match_alias_to_module() -> dict[str, list[str]]:
    '''
    This function builds a mapping of aliases to module names
    by inspecting the __aliases__ attribute of each module.
    '''
    alias_to_module = {}
    for module_name in real_py_class_filenames:
        try:
            import_string = f"bioinformatics_tools.file_classes.{module_name}"
            module = importlib.import_module(import_string)
            # Add the module name itself as an alias (case-insensitive)
            alias_to_module[module_name] = [module_name, module_name.lower()]
            LOGGER.debug('Loaded module: %s', module_name)
            # Add any defined aliases
            if hasattr(module, '__aliases__'):
                LOGGER.debug('Found aliases for %s: %s', module_name, module.__aliases__)
                if isinstance(module.__aliases__, list):
                    alias_to_module[module_name].extend(module.__aliases__)
                elif isinstance(module.__aliases__, str):
                    alias_to_module[module_name].append(module.__aliases__)
        except ModuleNotFoundError as e:
            LOGGER.info('Could not load aliases for %s: %s', module_name, e)
            raise e  # TODO - our own exception here
    return alias_to_module


def find_file_type(args: list) -> None | str:
    '''
    This function takes in a list of arguments and determines what type of file
    it is. It then returns the class that can handle that file.
    '''
    type_ = None
    for cnt, arg in enumerate(args):
        if arg.startswith('type:'):
            type_ = args[cnt + 1]
            type_ = type_.lower()
            break
    return type_


# def cli(Session):  #TODO: Inherit a method for CLI to make it easier to init & config app stuff
def cli():
    '''Command line interface for the script.
    '''
    # Step 0 - Configure/init logging
    config_logging_for_app()

    # Step 1 - Parse command line for "type"
    matched = False
    type_ = find_file_type(sys.argv)
    alias_to_module = match_alias_to_module()
    LOGGER.debug('Recognize file type: %s', type_)
    # Step 2 - Match command line to available programs (i.e., type: fasta)
    if type_:
        for module_str, type_identifier in alias_to_module.items():
            if type_.lower() in type_identifier:
                matched = True
                LOGGER.debug('✅ Recognized type (%s) and matched to module', type_)
                import_string = f"bioinformatics_tools.file_classes.{module_str}"
                LOGGER.debug('📦 Importing %s', import_string)
                current_module = importlib.import_module(import_string)
                CurrentClass = None
                for type_id in type_identifier:
                    if getattr(current_module, type_id, None):
                        LOGGER.debug('Using alias %s to refer to module %s', type_id, module_str)
                        CurrentClass = getattr(current_module, type_id)
                        break
                if CurrentClass is None:
                    LOGGER.error('Could not find a class in module %s that matches any of the aliases %s', module_str, type_identifier)
                    sys.exit(1)  #TODO: Show a report here
                # Controlling the execution of the class
                data = CurrentClass()  # Shows config
                if not data.valid:  #TODO: Nest this inside of data.run()
                    LOGGER.debug('File provided failed validation test')
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
