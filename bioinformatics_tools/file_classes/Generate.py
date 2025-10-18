'''
TODO: This module is a placeholder and a work in progress.
Module that allows you to generate miscellaneous files that don't have a dedicated class,
as defined by type: <filetype> in the config file or command line.
Not sure exactly where I was going with this...
'''
from datetime import datetime
import pathlib

from bioinformatics_tools.file_classes.base_classes import BioBase, command
from bioinformatics_tools.caragols.clix import LOGGER

__aliases__ = ['gen']

class Generate(BioBase):
    '''
    Class to generate miscellaneous files that don't have a dedicated class,
    as defined by type: <filetype> in the config file or command line.
    '''

    def __init__(self, file=None, detect_mode="medium") -> None:
        super().__init__(file=file, detect_mode=detect_mode, filetype='n/a')
        
        # --------------------------- Class-specific stuff --------------------------- #
        self.known_extensions.extend(['.csv', '.txt'])
        self.preferred_extension = '.txt'
        self.valid = True  # Bypass the default self.valid

        # ------------------- Filename and Content Validation Stuff ------------------ #
        self.preferred_file_path = self.clean_file_name()

    @command
    def do_create_slurm(self, barewords, **kwargs):
        '''
        Create a slurm script for the user with default parameters, or specify your own.

        Parameters:
        - memory: Memory in GB (default: 2)
        - threads: Number of threads (default: 1)
        - time: Time in hours (default: 4)
        - account: Slurm account (default: 'standby')

        Returns:
            int: The total number of sequences.
        '''
        LOGGER.info(f'CONFIGURATION: {self.conf.show()}')
        output = self.conf.get('output', None)
        if not output:
            date_string = datetime.now().strftime("%d%b%Y-%H%M")
            # output = self.preferred_file_path
            output = f"slurm_script-{date_string}.sh"
        output = pathlib.Path(output)
        LOGGER.info(f'Output file: {output.resolve()}')

        defaults = {
            'account': 'standby',
            'memory': 2,   # GB
            'threads': 1,
            'time': 4,     # hours
        }

        # Build settings cleanly: keep defaults + override ONLY known keys
        settings = {key: self.conf.get(key, defaults[key]) for key in defaults}

        slurm_script = f"""#!/bin/bash
#SBATCH -A {settings['account']}
#SBATCH --nodes=1
#SBATCH --ntasks={settings['threads']}
#SBATCH --mem={settings['memory']}G
#SBATCH --time={settings['time']:02}:00:00

echo "Generated from Dane!"
# Start workflow here
"""
        output.write_text(slurm_script)
        self.succeeded(msg=f"Wrote output file to {output}")
