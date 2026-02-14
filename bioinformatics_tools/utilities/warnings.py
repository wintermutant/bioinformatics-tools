'''
General warnings to display
'''
import sys
from bioinformatics_tools import toolSets


def TooFewArgumentsWarning():
    sys.stdout.write('Not enough arguments provided.\n')
    sys.stdout.write('See below for a list of all available tools:\n\n')
    sys.stdout.write('\n'.join([f"{prg}: {toolSets[prg]}"
                                for prg in toolSets.keys()]) + '\n')
    sys.stdout.write('\n')
    return 0


def InvalidArgumentOrSubprogram(arg):
    sys.stdout.write('Unrecognized first positional argument.\n')
    sys.stdout.write(f'{arg} was provided and not recognized.\n')
    sys.stdout.write(f'Too see all subprograms, use the --list flag\n')
    return 0


def ExecutableNotFound(program):
    sys.stdout.write(f"The program: {program} was not found in your path.\n")
    return 0
