from bioinformatics_tools.file_classes.base_classes import BioBase, command

__aliases__ = ['bam', 'binaryalignmentmap']

class BAM(BioBase):
    '''
    Class definition of Variant Calling Format Files
    '''

    def __init__(self, file=None, detect_mode="medium") -> None:
        super().__init__(file, detect_mode, filetype='bam')
        
        # --------------------------- Class-specific stuff --------------------------- #
        self.known_extensions.extend(['.bam'])
        self.preferred_extension = '.bam'

        # ------------------------------- Custom stuff ------------------------------- #
        self.bamKey = {}
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
        '''NOT IMPLEMENTED YET'''
        response = 'Passing: TODO'
        self.succeeded(msg=f"{response}", dex=response)
    
    @command
    def do_write_table(self, barewords, **kwargs):
        '''NOT IMPLEMENTED YET'''
        response = 'Passing: TODO'
        self.succeeded(msg=f"{response}", dex=response)

    @command
    def do_get_longest_gene(self, barewords, **kwargs):
        '''NOT IMPLEMENTED YET'''
        response = 'Test function'
        self.succeeded(msg=f"{response}", dex=response)

