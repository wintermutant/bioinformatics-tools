import gzip
import mimetypes
import pathlib
import pandas as pd

from bioinformatics_tools.file_classes.base_classes import BioBase

__aliases__ = ['gtf', 'genetransfer']


class GeneTransferFormat(BioBase):
    '''
    Class definition of Gene Transfer Format Files
    '''

    def __init__(self, file=None, detect_mode="medium") -> None:
        super().__init__(file, detect_mode, filetype='genetransferformat')
        # Default values
        self.known_extensions.extend(['.gtf'])
        self.preferred_extension = '.gtf.gz'

        # Custom stuff
        self.gtfKey = {}
        self.written_output = []
        self.preferred_file_path = self.clean_file_name()

        self.valid_extension = self.is_known_extension()
        self.valid = self.is_valid()

    def validate(self, open_file, mode="medium"):
        '''
        NOT IMPLEMENTED YET
        '''
        return True

    # ~~~ Rewriting ~~~ #
    def do_write_confident(self, barewords, **kwargs):
        '''
        NOT IMPLEMENTED YET
        '''
        response = 'Passing: TODO'
        self.succeeded(msg=f"{response}", dex=response)
    
    def do_write_table(self, barewords, **kwargs):
        '''
        NOT IMPLEMENTED YET
        '''
        response = 'Passing: TODO'
        self.succeeded(msg=f"{response}", dex=response)

    def do_test_function(self, barewords, **kwargs):
        '''
        NOT IMPLEMENTED YET
        '''
        response = 'Test function'
        self.succeeded(msg=f"{response}", dex=response)

