import argparse
import getpass
import logging
from pathlib import Path
import sys

import bioinformatics_tools
from bioinformatics_tools.file_classes.Fasta import Fasta
from bioinformatics_tools.caragols.logger import config_logging_for_app

LOGGER = logging.getLogger(__name__)

def main():
    config_logging_for_app()
    startup_info = {
        'cwd': Path.cwd(),
        'user': getpass.getuser(),
        'argv': sys.argv,
        'package_version': bioinformatics_tools.__version__
    }
    LOGGER.debug(f'\nStartup:\n{startup_info}', extra={'startup_info': startup_info}) # user, cwd, sys.argv, app version


    input = args.Input
    output = args.Output
    print(f'Dealing with {input} and {output}')
    print(f'Adding to the class')
    mydata = Fasta(input)
    print(f'Class init successful')
    print(mydata.all_headers)
    return 0

def parse_args():
    parser = argparse.ArgumentParser(description="Parser")
    parser.add_argument("-i", "--Input",
                        help="Fasta files to parse (can be multiple)",
                        required=True)
    # parser.add_argument("-i", "--Input",
    #                     help="Fasta files to parse (can be multiple)",
    #                     required=True, nargs='*')
    parser.add_argument("-o", "--Output",
                        help="Output file to write to",
                        required=False)
    return parser




if __name__ == "__main__":
    print('Running in main!!!')
    parser = parse_args()
    args = parser.parse_args()
    print(args)
    main(args)
