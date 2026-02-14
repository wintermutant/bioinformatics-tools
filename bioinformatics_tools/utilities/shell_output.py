'''
Formatting output to shell
'''
import os
import sys

from bioinformatics_tools import toolSets


def printMainExecutableHelp(executable):
    file = os.path.basename(executable)
    sys.stdout.write(f"{toolSets[file]}\n\n")


def printAvailablePrograms(executable, programList):
    sys.stdout.write(f"Available programs to be called with {executable}:\n")
    for count, program in enumerate(sorted(programList)):
        sys.stdout.write(f"{count}: {program}\n")
    sys.stdout.write('\n')


def printSubprogramHelp(subprogram, programList):
    print(f'In printSubprogramHelp:\n{programList}\n{subprogram}')
    sys.stdout.write(f"{programList[subprogram]['help']}\n\n")
