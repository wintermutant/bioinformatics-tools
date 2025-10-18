'''
Class skeleton for new file types
'''
from bioinformatics_tools.file_classes.base_classes import BioBase, command


class ExampleClass(BioBase):
    '''
    Class definition of EXAMPLE files
    '''

    def __init__(self, file=None, detect_mode="medium") -> None:
        super().__init__(file, detect_mode, filetype='example')

        # --------------------------- Class-specific stuff --------------------------- #
        self.known_extensions.extend(['.example'])
        self.preferred_extension = '.example'

        # ------------------------------- Custom stuff ------------------------------- #
        self.exampleKey = {}
        self.written_output = []

        # ------------------- Filename and Content Validation Stuff ------------------ #
        self.preferred_file_path = self.clean_file_name()
        self.valid_extension = self.is_known_extension()
        self.valid = self.is_valid()

    def validate(self, open_file, mode="medium"):
        '''
        NOT IMPLEMENTED YET
        '''
        return True

    # ~~~ Rewriting ~~~ #
    @command
    def do_write_confident(self, barewords, **kwargs):
        '''
        NOT IMPLEMENTED YET
        Write the confident EXAMPLE file to disk using default extension
        '''
        response = 'Passing: TODO'
        self.succeeded(msg=f"{response}", dex=response)
    
    @command
    def do_write_table(self, barewords, **kwargs):
        '''
        NOT IMPLEMENTED YET
        Tabular EXAMPLE output
        '''
        response = 'Passing: TODO'
        self.succeeded(msg=f"{response}", dex=response)

    @command
    def do_get_longest_gene(self, barewords, **kwargs):
        '''
        NOT IMPLEMENTED YET
        Test function
        '''
        response = 'Test function'
        self.succeeded(msg=f"{response}", dex=response)

