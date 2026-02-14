# Command line utilities
import bioinformatics_tools.warnings as warnings
import shutil


def find_executable(program):
    '''
    '''
    value = shutil.which(program)
    return warnings.ExecutableNotFound(program) if value is None else value
