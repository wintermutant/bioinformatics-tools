'''
Class definition of General Feature Format version 3
'''
import pathlib

from bioinformatics_tools.file_classes.base_classes import BioBase, command

__aliases__ = ['gff', 'gff3']

class GeneralFeatureFormat(BioBase):
    '''
    Class definition of General Feature Format version 3
    (GFF3) files.
    '''

    def __init__(self, file=None, detect_mode="medium") -> None:
        super().__init__(file, detect_mode, filetype='generalfeatureformat')
        
        # --------------------------- Class-specific stuff --------------------------- #
        self.known_extensions.extend(['.gff', '.gff3', '.g3'])
        self.preferred_extension = '.gff3.gz'

        # ------------------------------- Custom Stuff ------------------------------- #
        self.gffKey = {}
        self.written_output = []

        # ------------------- Filename and Content Validation Stuff ------------------ #
        self.preferred_file_path = self.clean_file_name()
        self.valid_extension = self.is_known_extension()
        self.valid = self.is_valid()

    def validate(self, open_file, mode="medium"):
        if self.detect_mode == 'soft':
            return self.valid_extension

        line_count = 0
        valid = True
        line = next(open_file)
        while valid:
            line = line.strip()
            if line.startswith('#'):
                line = next(open_file)
                continue
            line_count += 1
            columns = line.split('\t')
            if not len(columns) == 9:
                valid = False
                break
            seqid, source, type_, start, end, score, strand, phase, attributes = columns
            seqid = seqid.strip()
            source = source.strip()
            type_ = type_.strip()
            try:
                start = int(start)
                end = int(end)                
            except ValueError:
                print(f'DEBUG: Error in line {line_count}: Start or End invalid integer')
                valid = False
                break

            if not phase == '.':
                try:
                    phase = int(phase)
                except ValueError:
                    print(f'DEBUG: Error in line {line_count}: Phase invalid integer')
                    valid = False
                    break
            if not score == '.':                
                try:
                    score = float(score)
                except ValueError:
                    print(f'DEBUG: Error in line {line_count}: Score invalid float')
                    valid = False
                    break

            if phase not in [0, 1, 2, '.']:
                print(f'DEBUG: Error in line {line_count}: Phase must be 0, 1, 2, or "."')
                valid = False
                break

            if strand not in ['+', '-', '.']:
                print(f'DEBUG: Error in line {line_count}: Strand must be +, -, or "."')
                valid = False
                break
            self.gffKey[line_count] = (seqid, source, type_, start, end, score, strand, phase, attributes)

            try:
                line = next(open_file)
            except StopIteration:
                break
        return valid

    # --------------------------------- Rewriting -------------------------------- #
    @command
    def do_write_confident(self, barewords, **kwargs):
        '''Write the confident GFF3 file to disk using default extension'''
        if not self.valid:
            response = 'File is not valid'
            self.failed(msg=f"{response}")

        output = self.conf.get('output', None)
        if not output:
            output = self.preferred_file_path
        output = pathlib.Path(output)

        if output.suffix in ['.gz', '.gzip']:
            with gzip.open(str(self.preferred_file_path), 'wt') as open_file:
                for _, value in self.gffKey.items():
                    open_file.write(f'{value[0]}\t{value[1]}\t{value[2]}\t{value[3]}\t{value[4]}\t{value[5]}\t{value[6]}\t{value[7]}\t{value[8]}\n')
        else:
            with open(str(output), 'w') as open_file:
                for _, value in self.gffKey.items():
                    open_file.write(f'{value[0]}\t{value[1]}\t{value[2]}\t{value[3]}\t{value[4]}\t{value[5]}\t{value[6]}\t{value[7]}\t{value[8]}\n')
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
            output = self.preferred_file_path
        output = pathlib.Path(output)

        if output.suffix in ['.gz', '.gzip']:
            with gzip.open(str(self.preferred_file_path), 'wt') as open_file:
                open_file.write(f'seqid,source,type,start,end,score,strand,phase,attributes\n')
                for _, value in self.gffKey.items():
                    open_file.write(f'{value[0]},{value[1]},{value[2]},{value[3]},{value[4]},{value[5]},{value[6]},{value[7]},{value[8]}\n')
        else:
            with open(str(output), 'w') as open_file:
                open_file.write(f'seqid,source,type,start,end,score,strand,phase,attributes\n')
                for _, value in self.gffKey.items():
                    open_file.write(f'{value[0]},{value[1]},{value[2]},{value[3]},{value[4]},{value[5]},{value[6]},{value[7]},{value[8]}\n')
        response = 'Wrote the output file'
        self.succeeded(msg=f"{response}", dex=response)

    @command
    def do_get_longest_gene(self, barewords, **kwargs):
        '''
        Get the longest gene in the GFF3 file.
        '''
        longest_gene = None
        max = 0
        for index, entry in self.gffKey.items():
            gene_length = entry[4] - entry[3]
            if gene_length > max:
                max = gene_length
                longest_gene = entry
        data = longest_gene
        self.succeeded(msg=f"Longest gene:\n{data}", dex=data)

