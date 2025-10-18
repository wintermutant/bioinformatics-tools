import gzip
import pathlib
import typer

import pandas as pd

from bioinformatics_tools.file_classes.base_classes import BioBase, command


class Fastq(BioBase):
    '''
    Class for Fastq Files!
    '''

    def __init__(self, file=None, detect_mode="medium") -> None:
        super().__init__(file=file, detect_mode=detect_mode, filetype='fastq')
        
        # --------------------------- Class-specific stuff --------------------------- #
        self.known_extensions.extend(['.fastq', '.fq'])
        self.preferred_extension = '.fastq.gz'

        # ------------------------------- Custom Stuff ------------------------------- #
        self.fastqKey = {}
        self.written_output = []

        # ------------------- Filename and Content Validation Stuff ------------------ #
        self.preferred_file_path = self.clean_file_name()
        self.valid_extension = self.is_known_extension()
        self.valid = self.is_valid()

    def validate(self, open_file, mode="medium"):
        '''
        Validate the Fastq file and hydrate self.fastqKey, a dictionary of the fastq file
        in the form:
        {entry_index: (header1, sequence, header2, quality)}
        '''
        if self.detect_mode == 'soft':
            return self.valid_extension

        # Content Stuff
        valid_chars = set('ATGCNatgcn')
        valid_qchars = '!"#$%&()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~'
        valid_qchars += "'"

        line_count = 0
        valid = True
        line = next(open_file)

        entry_count = 0
        while valid:
            line = line.strip()
            line_count += 1
            if line_count % 4 == 1:
                if not line.startswith('@'):
                    print(f"DEBUG: Error on line {line_count}: Header line must start with '@'")
                    valid = False
                    return False
                current_header_1 = line
            elif line_count % 4 == 2:
                if not set(line).issubset(valid_chars):
                    print(f"DEBUG: Error on line {line_count}: Sequence line contains invalid characters")
                    valid = False
                seqlen = len(line)
                current_seq = line
            elif line_count % 4 == 3:
                if not line.startswith('+'):
                    print(f"DEBUG: Error on line {line_count}: Separator line must start with '+'")
                    valid = False
                current_header_2 = line
            elif line_count % 4 == 0:
                if not set(line).issubset(valid_qchars):
                    print(f"DEBUG: Error on line {line_count}: Quality line contains invalid characters")
                    valid = False
                elif seqlen != len(line):
                    print(f"DEBUG: Error on line {line_count}: Quality line length does not match sequence line length")
                    valid = False
                else:
                    current_qual = line
                    seqlen = -1
                    self.fastqKey[entry_count] = (current_header_1, current_seq, current_header_2, current_qual )
                    entry_count += 1
            try:
                line = next(open_file)
            except StopIteration:
                if line_count % 4 != 0:
                    print(f"DEBUG: Error on line {line_count}: File ended in the middle of a record")
                    valid = False
                break


        return valid
    
    # ------------------------------- File Writing ------------------------------- #
    @command
    def do_write_confident(self, barewords, **kwargs):
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
                open_file.write('defline,sequence,defline2,quality\n')
                for key, value in self.fastqKey.items():
                    open_file.write(f'{value[0]}\n{value[1]}\n{value[2]}\n{value[3]}\n')
        else:
            with open(str(output), 'w', encoding='utf-8') as open_file:
                open_file.write('defline,sequence,defline2,quality\n')
                for _, value in self.fastqKey.items():
                    open_file.write(f'{value[0]}\n{value[1]}\n{value[2]}\n{value[3]}\n')
        response = 'Wrote the output file'
        self.succeeded(msg=f"{response}", dex=response)
    
    @command
    def do_write_table(self, barewords, **kwargs):
        '''Tabular output'''
        if not self.valid:
            response = 'File is not valid'
            self.failed(msg=f"{response}")

        output = self.conf.get('output', None)
        if not output:
            print(f'Self.file_path: {self.file_path}')
            output = self.file_path.stem + '-VALIDATED.txt.gz'
        output = pathlib.Path(output)

        if output.suffix in ['.gz', '.gzip']:
            with gzip.open(str(self.preferred_file_path), 'wt') as open_file:
                open_file.write('defline,sequence,defline2,quality\n')
            # with gzip.open(str(output), 'wt') as open_file:
                for _, value in self.fastqKey.items():
                    open_file.write(f'{value[0]},{value[1]},{value[2]},{value[3]}\n')
        else:
            with open(str(output), 'w', encoding='utf-8') as open_file:
                print(f'Opening {output} for writing')
                open_file.write('defline,sequence,defline2,quality\n')
                for key, value in self.fastqKey.items():
                    open_file.write(f'{value[0]},{value[1]},{value[2]},{value[3]}\n')
        response = 'Wrote the output file'
        self.succeeded(msg=f"{response}", dex=response)

    @command
    def do_grab_first_record(self, barewords, **kwargs):
        '''
        Returns the first record in the fastq file
        '''
        data = self.fastqKey[0]
        self.succeeded(
            msg=f"First record:\n{data}", dex=data)
        return 0

    @command
    def do_all_headers(self, barewords, **kwargs):
        '''
        Shows all headers in the fastq file
        '''
        data = [v[0] for k, v in self.fastqKey.items()]
        self.succeeded(
            msg=f"All headers:\n{data}", dex=data)
        return 0
    
    @command
    def do_seqlengths(self, barewords, **kwargs):
        '''
        Return all of the seqlengths in the fastq file
        '''
        seqlens = set()
        for k, v in self.fastqKey.items():
            seqlens.add(len(v[1]))
        data = seqlens
        self.succeeded(
            msg=f"All sequence lengths:\n{data}", dex=data)
        return 0
    
    @command
    def do_gc_content(self, barewords, precision: int = 2, **kwargs):
        '''
        Return the GC content for each record in the fastq file
        '''
        precision = int(self.conf.get('precision', precision))
        gcContent = {}
        for cnt, items in self.fastqKey.items():
            seq = items[1].upper()
            gc_count = seq.count('G') + seq.count('C')
            percent = round((gc_count) / len(seq), precision)
            gcContent[cnt] = (items[0], percent)
        data = gcContent
        self.succeeded(
            msg=f"All GC Content:\n{data}", dex=data)
        return 0

    @command
    def do_gc_content_total(self, barewords, precision: int = 2, **kwargs):
        '''
        Get the total GC content for the fastq file
        '''
        precision = int(self.conf.get('precision', precision))
        values = []
        print(f'Self.fastqKey: {self.fastqKey}')
        for cnt, items in self.fastqKey.items():
            seq = items[1].upper()
            print(f'Seq: {seq}')
            gc_count = seq.count('G') + seq.count('C')
            gc_content = (gc_count / len(seq)) * 100 if len(seq) > 0 else 0
            values.append(round(gc_content, precision))
        data = round(sum(values) / len(values), precision) if values else 0

        if kwargs.get('internal_call', False):
            return data
        self.succeeded(
            msg=f"Total GC content: {data}", dex=data)
        return 0

    @command
    def do_total_seqs(self, barewords, **kwargs):
        '''Return the total number of sequences (aka, entries) in the fasta file'''
        data = len(self.fastqKey.keys())
        if kwargs.get('internal_call', False):
            return data
        self.succeeded(msg=f"Total sequences: {data}", dex=data)

    @command
    def do_total_seq_length(self, barewords, **kwargs):
        '''Return the total length of all sequences in the fasta file'''
        data = sum([len(v[1]) for k, v in self.fastqKey.items() ])
        if kwargs.get('internal_call', False):
            return data
        self.succeeded(msg=f"Total sequence length: {data}", dex=data)
    
    @command
    def do_basic_stats(self, barewords, **kwargs):
        '''Return basic statistics of the fasta file'''
        data = {
            'Total Sequences': self.do_total_seqs(barewords, internal_call=True),
            'Total Sequence Length': self.do_total_seq_length(barewords, internal_call=True),
            'Total GC Content': self.do_gc_content_total(barewords, internal_call=True)
        }
        self.succeeded(msg=f"Basic statistics:\n{data}", dex=data)
