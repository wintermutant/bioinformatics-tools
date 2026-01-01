'''
Module for all things fasta
'''
import gzip
import logging
import pathlib
import sys
from uuid import UUID, uuid4

import typer
from pydantic import BaseModel, Field
from pydantic_sqlite import DataBase

from bioinformatics_tools.file_classes.base_classes import BioBase, command

LOGGER = logging.getLogger(__name__)


class FastaRecord(BaseModel):
    '''Class representing a single FASTA record'''
    uuid: UUID = Field(default_factory=uuid4, alias='uuid')
    filename: str
    description: str
    sequence: str


class DbLogRecord(BaseModel):
    '''Additional mandatory log information that gets written as a table into the database'''
    uuid: UUID = Field(default_factory=uuid4, alias='uuid')
    file_name: str
    file_path_original: str
    logs: list[str]
    notes: str


class Fasta(BioBase):
    '''Class for Fasta Files
    '''
    # known_extensions = ['.fna', '.fasta', '.fa']
    # known_compressions = ['.gz', '.gzip']
    # preferred_extension = '.fasta.gz'

    available_rules = ['rule_a', 'rule_b', 'rule_d']
    outputs = ['-SIMPLIFIED.fasta', ]
    ruleToOutput = {
        'rule_a': ('-SIMPLIFIED.fasta'),
        'rule_b': ('-UNSIMPLIFIED.fasta')
    }

    def __init__(self, file=None, detect_mode="medium", run_mode='cli') -> None:
        self.file, self.detect_mode, self.run_mode = file, detect_mode, run_mode
        if self.run_mode == 'cli':
            super().__init__(detect_mode=detect_mode, run_mode=run_mode, filetype='fasta')
        elif self.run_mode == 'module' and self.file:
            LOGGER.debug('Not running in cli mode')
            self.file_path = pathlib.Path(self.file)
            self.file_name = self.file_path.name
        else:
            LOGGER.warning('No file detected, triggering sys.exit within module...')
            sys.exit('Error: When running in module mode, a file must be provided')
       
        # --------------------------- Class-specific stuff --------------------------- #
        self.known_extensions.extend(['.fna', '.fasta', '.fa'])
        self.preferred_extension = '.fasta.gz'

        # ------------------------------- Custom stuff ------------------------------- #
        self.fastaKey: dict[int, tuple[str, str]] = {}  #TODO change this to a generic
                                # eventually each class can have a data model with a generic
                                # name and point to a Pydantic model
        self.written_output = []

        # --------------------------- Filename and Content Validation stuff --------------------------- #   
        self.preferred_file_path = self.clean_file_name()
        self.valid_extension = self.is_known_extension()
        self.valid = self.is_valid()

    def validate(self, open_file, mode="medium") -> bool:
        '''
        Validate the Fasta file and hydrate self.fastaKey, a dictionary of the fasta file
        in the form:
        {entry_index: (header, sequence)}
        '''
        if self.detect_mode == 'soft':
            LOGGER.debug('Detecting in soft mode, only checking extension')
            return self.valid_extension
        LOGGER.debug('Detecting comprehensively')

        valid_chars = set('ATGCNatgcn')
        prev_header = False
        current_header = ''
        current_seq = ''
        cnt = 0
        try:
            line = next(open_file)
        except StopIteration:
            return False
        while line:
            line = line.strip()
            if not line:
                line = next(open_file)
                continue
            if line.startswith('>'):
                cnt += 1
                current_header = line.strip()
                current_seq = ''
                if prev_header:
                    LOGGER.error('2 headers in a row')
                    self.fastaKey = {}
                    return False
                prev_header = True
                line = next(open_file)
            else:
                while line and not line.startswith('>'):
                    if not set(line).issubset(valid_chars):
                        LOGGER.error('Line has invalid character: %s', line)
                        return False
                    else:
                        current_seq += line.strip()
                        try:
                            line = next(open_file).strip()
                        except StopIteration:
                            line = None
                self.fastaKey[cnt] = (self.clean_header(current_header), current_seq.upper())

                prev_header = False

        return True

    # Database stuff
    def to_pydantic(self) -> list[FastaRecord]:
        '''Turn the fasta file into a valid pydanic model
        TODO: Add a checksum sometime'''
        LOGGER.info('Filename: %s Filepath: %s full path: %s', self.file_name, self.file_path, self.file_path.resolve())
        return [FastaRecord(filename=self.file_name, description=header, sequence=seq) for header, seq in self.fastaKey.values()]

    def logs_to_pydantics(self, notes: str = '') -> DbLogRecord:
        '''Convert session logs to a DbLogRecord for database insertion'''
        return DbLogRecord(
            file_name=self.file_name,
            file_path_original=str(self.file_path.resolve()),
            logs=self.log_handler.log_records,
            notes=notes
        )

    @command
    def do_write_db(self, **kwargs):
        '''Write the fasta records to a sqlite database
        2 Steps (third for consideration?):
        1) Write the contents for the database
        2) Add in the log information
        3)? Copy in the configuration?
        '''
        db_path = self.conf.get('fasta.write_db.db_path', f'fasta_records-{self.timestamp}.db')
        db = DataBase(db_path)

        # Write fasta records
        records = self.to_pydantic()
        for record in records:
            db.add('fasta_records', record)

        # Write session logs
        notes = self.conf.get('notes', '')
        log_record = self.logs_to_pydantics(notes=notes)
        db.add('logs', log_record)

        self.succeeded(msg=f"{len(records)} records and {len(log_record.logs)} log entries written to database at {db_path}")

    @command
    def do_add_to_db(self, db_path: str = typer.Option(None),  **kwargs):
        '''Add the fasta records to an existing sqlite database'''
        db_path = self.conf.get('fasta.add_to_db.db_path', None)
        if not db_path:
            self.failed(msg='No db_path provided. Please use db_path: <path_to_db>')
        db = DataBase(db_path)
        records = self.to_pydantic()
        for record in records:
            db.add('fasta_records', record)
        self.succeeded(msg=f"{len(records)} records added to database at {db_path}")
        

    # ~~~ Rewriting ~~~ #
    @command
    def do_write_confident(self, **kwargs):
        '''
        Here, we always want the same extension and compression: .fasta.gz
        We also want to ensure only ATGCN and each sequence is on 1 line
        '''
        if not self.valid:
            response = 'File is not valid'
            self.failed(msg=f"{response}")

        output = self.conf.get('output', None)
        if not output:
            output = self.preferred_file_path
        output = pathlib.Path(output)
        if output.suffix in ['.gz', '.gzip']:
            with gzip.open(str(self.preferred_file_path), 'wt') as open_file:
                for _, value in self.fastaKey.items():
                    open_file.write(f'>{value[0]}\n{value[1]}\n')
        else:
            with open(str(output), 'w', encoding='utf-8') as open_file:
                for _, value in self.fastaKey.items():
                    open_file.write(f'>{value[0]}\n{value[1]}\n')

        self.succeeded(msg=f"Wrote output file to {output}")

    @command
    def do_write_table(self, **kwargs):
        '''Tabular output'''
        if not self.valid:
            response = 'File is not valid'
            self.failed(msg=f"{response}")

        output = self.conf.get('output', None)
        if not output:
            output = self.file_path.stem + '-VALIDATED.txt.gz'
        output = pathlib.Path(output)

        if output.suffix in ['.gz', '.gzip']:
            with gzip.open(str(output), 'wt') as open_file:
                for _, value in self.fastaKey.items():
                    open_file.write(f'{value[0]},{value[1]}\n')
        else:
            with open(str(output), 'w') as open_file:
                for key, value in self.fastaKey.items():
                    open_file.write(f'{value[0]},{value[1]}\n')
        self.succeeded(msg=f"Wrote output file to {output}", dex=response)

    @command
    def do_write_binid(self, **kwargs):
        # TODO: Change the name of this
        '''Create a bin ID file from the fasta file in the form: header,filename\n'''
        output = self.conf.get('output', None)
        if not output:
            output = self.file_path.with_name(f'{self.basename}-BinID.txt.gz')
        output = pathlib.Path(output)

        if output.suffix in ['.gz', '.gzip']:
            with gzip.open(str(output), 'wt') as open_file:
                for _, value in self.fastaKey.items():
                    open_file.write(f'{value[0]},{self.file_name}\n')
        else:
            with open(str(output), 'w') as open_file:
                for _, value in self.fastaKey.items():
                    open_file.write(f'{value[0]},{self.file_name}\n')
        data = None
        self.succeeded(msg=f"Wrote the binID file to {output}", dex=data)

    # ~~~ Common Properties ~~~ #
    @staticmethod
    def clean_header(header: str) -> str:
        '''Remove headers initial > and replace spaces with _
        Some programs don't like spaces in headers'''
        if header.startswith('>'):
            clean_header = header[1:]
        else:
            clean_header = header
        clean_header = clean_header.replace(' ', '_')
        return clean_header

    # PROPERTIES
    @command
    def do_all_headers(self, **kwargs):
        '''Return all headers to standard out'''
        data = [v[0] for k, v in self.fastaKey.items()]
        self.succeeded(msg=f"All headers:\n{data}", dex=data)

    @command
    def do_all_seqs(self, **kwargs):
        '''Return all sequences to standard out'''
        data = [v[1] for k, v in self.fastaKey.items()]
        self.succeeded(msg=f"All sequences:\n{data}", dex=data)

    # @command
    # def do_annotate_data(self, argument: str = 'Dane'):
    #     '''Return all sequences to standard out'''
    #     data = 'work in progress'
    #     self.succeeded(msg=f"All sequences:\n{data}", dex=data)

    @command
    def do_gc_content(self, precision: int = 2, **kwargs):
        '''Return the GC content of each sequence in the fasta file'''
        # precision = int(self.conf.get('fasta.gc_content.precision', precision))
        precision = 2
        gc_content = {}
        print('INSIDEEE and outside')
        print(f'Self.fastakey.items(): {self.fastaKey}')
        for cnt, items in self.fastaKey.items():
            seq = items[1].upper()
            gc_count = seq.count('G') + seq.count('C')
            percent = round((gc_count) / len(seq), precision)
            gc_content[cnt] = (items[0], percent)
        data = gc_content
        self.succeeded(msg=f"GC Content per entry:\n{data}", dex=data)
        if kwargs.get('origin') == 'api':
            return {'results': data}

    @command
    def do_gc_content_total(self, precision: int = 2, **kwargs) -> dict | None:
        '''Return the average GC content across all sequences in the fasta file
        '''
        # Get precision from CLIX configuration (handles precision: 4 syntax)
        # precision = int(self.conf.get('precision', precision))
        values = []
        for _, items in self.fastaKey.items():
            seq = items[1].upper()
            gc_count = seq.count('G') + seq.count('C')
            gc_content = (gc_count / len(seq)) * 100 if len(seq) > 0 else 0
            values.append(round(gc_content, precision))
        data = round(sum(values) / len(values), precision) if values else 0
        if kwargs.get('origin') == 'api':
            print('Calling from API...')
            return {'results': data}
        self.succeeded(msg=f"Total GC Content: {data}", dex=data)

    @command
    def do_total_seqs(self, **kwargs) -> int | None:
        '''Return the total number of sequences (entries) in the fasta file.'''
        data = len(self.fastaKey.keys())
        LOGGER.info('KWARgs: %s', kwargs)
        if kwargs.get('internal_call', False):
            return data
        self.succeeded(msg=f"Total sequences: {data}", dex=data)
        return None

    @command
    def do_total_seq_length(self, **kwargs):
        '''Return the total length of all sequences in the fasta file'''
        # TODO:  ignore_size: int = 0
        data = sum([len(v[1]) for k, v in self.fastaKey.items() ])
        if kwargs.get('internal_call', False):
            return data
        self.succeeded(msg=f"Total sequence length: {data}", dex=data)

    # @command(aliases=['filter length', 'filter'])
    @command
    def do_filter_seqlength(
        self,
        min_length: int = typer.Option(2000, "--min-length", "-l", help="Minimum sequence length to keep"),
        output_file: str = typer.Option(None, "--output", "-o", help="Output file path"),
        **kwargs
    ) -> None:
        '''Filter the sequences by length, keeping only sequences above the minimum length'''
        seqlength = self.conf.get('seqlen', 2000)
        output = self.conf.get('output', None)
        if not output:
            output = self.file_path.with_name(f'{self.basename}-FILTERED-{seqlength}bp.txt')

        with open(output, 'wt', encoding="utf-8") as open_file:
            for cnt, items in self.fastaKey.items():
                if len(items[1]) > seqlength:
                    writeline = f'>{items[0]}\n{items[1]}\n'
                    open_file.write(writeline)
        data = {'seqlength': seqlength, 'output': output, 'action': 'filter_seqlength'}
        msg = f'Processed with seqlength of {seqlength} and wrote to output: {output}'
        self.succeeded(msg=f"{msg}", dex=data)
    
    @command
    def do_n_largest_seqs(
        self,
        n: int = typer.Option(10, "--count", "-n", help="Number of largest sequences to return"),
        output_file: str = typer.Option(None, "--output", "-o", help="Output file path"),
        **kwargs
    ):
        '''Return the n largest sequences in the fasta file'''
        # FIXME: What's confusing is we have the argument "n" like the user adds the -n int flag, but we don't
        # actually grab n as usual. This is due to caragols setting it in self.conf[n] = int
        n = int(self.conf.get('n', 10))
        output = self.conf.get('output', None)
        if not output:
            output = self.file_path.with_name(f'{self.basename}-LARGEST-{n}.txt')

        sorted_values = self.sorted_fasta
        with open(output, 'wt', encoding="utf-8") as open_file:
            for count, (index, (header, seq)) in enumerate(sorted_values.items()):
                if count >= n:
                    break
                writeline = f'>{header}\n{seq}\n'
                open_file.write(writeline)
        self.succeeded(msg='Success: File created', dex=None)

    @command
    def do_seq_length(self, **kwargs):
        '''Return the length of a specific sequence'''
        data = {(k, v[0]): len(v[1]) for k, v in self.fastaKey.items()}
        if kwargs.get('internal_call', False):
            return data
        self.succeeded(msg=f"Total sequence length: {data}", dex=data)

    @command
    def do_search_subsequence(
        self,
        subsequence: str = typer.Argument(..., help="DNA/RNA subsequence to search for"),
        # case_sensitive: bool = typer.Option(False, "--case-sensitive", help="Perform case-sensitive search"),  # TODO: Add this functionality
        **kwargs
    ):
        '''Search for a subsequence in all sequences of the fasta file'''
        subsequence = self.conf.get('subsequence', None)
        if not subsequence:
            self.failed(msg='No subsequence provided. Please use subsequence: <subsequence>')
        results = {}
        for k, v in self.fastaKey.items():
            if subsequence in v[1]:
                results[k] = v
        data = results
        self.succeeded(msg=f"The following entries contained the subsequence:\n{data}", dex=data)
    
    def do_basic_stats(self, **kwargs):
        '''Return basic statistics of the fasta file'''
        data = {
            'Total Sequences': self.do_total_seqs(internal_call=True),
            'Total Sequence Length': self.do_total_seq_length(internal_call=True),
            'Total GC Content': self.do_gc_content_total(internal_call=True)
        }
        self.succeeded(msg=f"Basic statistics:\n{data}", dex=data)

    @property
    def sorted_fasta(self):
        ascending = self.conf.get('ascending', False)
        if not ascending:
            return dict(sorted(self.fastaKey.items(), key=lambda item: item[1][0].lower()))
        return dict(sorted(self.fastaKey.items(), key=lambda item: item[1][0].lower()), reverse=True)
