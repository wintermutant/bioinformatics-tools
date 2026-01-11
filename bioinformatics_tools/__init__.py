
__version__ = '0.3.1b1'


main_help = "A suite of tools used during various bioinformatic analyses."

toolSets = {
    'alignmentTools': 'Tools used during alignment',
    'annotationTools': 'Tools used during annotation',
    'fastaTools': 'Tools used for with fasta as input',
    'misc_tools': 'Tools with miscellaneous uses',
    'xTools.py': "Example for dev"}

# Dictionaries for each executable script to find their programs

alignmentTools_programs = {
    'filterBamByReference': (
        {'help': ('ADD TO THIS')}
    ),
    'samThresholdFilter': (
        {'help': ('ADD TO THIS')}
    ),
}


annotationTools_programs = {
    'createVanillaGFF': (
        {'help': ('Given a multi - fasta file, create a < vanilla > GFF file '
                  'that can be utilized by programs like HTSeqCount to get'
                  'counts per feature.')}
    ),
    'gffMine': (
        {'help': 'This is the help for gffMine'}
    ),
    'trimGFFByFeature': (
        {'help': 'This is the help for trimGFFByFeature'}
    ),
    'writeFlaggedContigsNewBinID': (
        {'help': 'This is the help for writeFlaggedContigsNewBinID'}
    ),
    'writeModeGFFFeaturePerBin': (
        {'help': 'This is the help for writeModeGFFFeaturePerBin'}
    ),
    'writeTaxonRemovedFastas': (
        {'help': 'This is the help for gffMine'}
    ),
}


fastaTools_programs = {
    'example': (
        {'help': 'Example to integrate SnakeMake'}
    ),
    'calcBinsetLengths': (
        {'help': 'Output tab-delimited file summarizing fasta \
length and number of contigs'}
    ),
    'combineMultipleFastas': (
        {'help': 'Combine multiple fasta files'}
    ),
    'revertBinIdToOriginal': (
        {'help': 'Given a bin identification file and an assembly,\
write fasta files to the current directory.'}
    ),
    'compareTwoBinFiles': (
        {'help': 'ADD TO THIS'}
    ),
    'createBinID': (
        {'help': 'Create a bin identification file from a set of fastas \
and a corresponding assembly.'}
    ),
    'fastaToFaa': (
        {'help': 'Convert a FASTA file to FAA format. Reading frame by \
default is 0.'}
    ),
    'fastaStats': (
        {'help': 'This is the help for fastaStats'}
    ),
    'filterAssembly': (
        {'help': 'ADD TO THIS'}
    ),
    'filterSeqlength': (
        {'help': 'ADD TO THIS'}
    ),
    'grabEntryDiffs': (
        {'help': 'ADD TO THIS'}
    ),
    'magBinMatrix': (
        {'help': 'ADD TO THIS'}
    ),
    'pfamTigrfamProcessingAnvio': (
        {'help': 'ADD TO THIS'}
    ),
    'split_multifasta': (
        {'help': 'ADD TO THIS'}
    ),
    'splitFastaByHeader': (
        {'help': 'ADD TO THIS'}
    ),
    'tetranucleotideFreq': (
        {'help': 'Help for tetranucleotideFreq'}
    ),
    'writeFastaFromBinID': (
        {'help': 'ADD TO THIS'}
    ),
    'writeLargestSequences': (
        {'help': 'ADD TO THIS'}
    ),
}


misc_tools_programs = {
    'appendBinID': (
        {'help':
         'Program that will append the bin identification a new field in a file \
delimited by a specified character. User must specify which field will \
be used for comparison and the delimiter.'}
    ),
    'CatToBatOutputConverter': (
        {'help': 'ADD TO THIS'}
    ),
    'compare2BinIDs': (
        {'help': 'ADD TO THIS'}
    ),
    'constrainsUniGCodeParser': (
        {'help': 'ADD TO THIS'}
    ),
    'convertTPM': (
        {'help': 'ADD TO THIS'}
    ),
    'dnaDiffCrawler': (
        {'help': 'ADD TO THIS'}
    ),
    'grabCheckMOut': (
        {'help': 'ADD TO THIS'}
    ),
    'KeggTranslator': (
        {'help': 'ADD TO THIS'}
    ),
    'mergeCounts': (
        {'help': 'ADD TO THIS'}
    ),
    'processMetaphlanOutput': (
        {'help': 'ADD TO THIS'}
    ),
    'recursivelyMoveFiles': (
        {'help': 'ADD TO THIS'}
    ),
    'subjectEncryption': (
        {'help': 'ADD TO THIS'}
    ),
    'vcf_filter': (
        {'help': 'ADD TO THIS'}
    ),
}
