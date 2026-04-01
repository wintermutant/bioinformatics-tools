"""
All MARGIE rules. No games.
"""
import os
import sys

# Add current directory to path to import workflow_helpers
sys.path.insert(0, os.path.dirname(workflow.snakefile))
from workflow_helpers import rc, fixed_path, build_filepath, db_token

WORKFLOW_DIR = os.path.dirname(workflow.snakefile)

# ─────────────────────── Path Definitions ─────────────────────── #
# Single source of truth for all file paths. Change paths here, not in rules.

# Common paths
INPUT_FASTA = rc('input_fasta', config=config)
MAIN_DATABASE = rc('main_database', config=config)
LOAD_SCRIPT = os.path.join(WORKFLOW_DIR, "load_to_db.py")

# Prodigal outputs
PRODIGAL_GFF = build_filepath('prodigal.output', 'gff', config=config)
PRODIGAL_FAA = build_filepath('prodigal.output', 'faa', config=config)
PRODIGAL_TOKEN = db_token('prodigal', config=config)

# Pfam outputs
PFAM_TSV = fixed_path('pfam/pfam.tsv', config=config)
PFAM_TOKEN = db_token('pfam', config=config)

# COG outputs
COG_CLASSIFY = fixed_path('cog/cog_classify.tsv', config=config)
COG_COUNTS = fixed_path('cog/cog_count.tsv', config=config)
COG_TKN = fixed_path('cog/cog.tkn', config=config)
COG_TOKEN = db_token('cog', config=config)

# KOFam outputs
KOFAM_TSV = fixed_path('kofam/kofam.tsv', config=config)
KOFAM_TOKEN = db_token('kofam', config=config)

# Uniop outputs
UNIOP_OPERONS = fixed_path('uniop/operons.tsv', config=config)
UNIOP_TOKEN = db_token('uniop', config=config)

# dbCAN outputs
DBCAN_OVERVIEW = fixed_path('dbcan/overview.tsv', config=config)
DBCAN_TOKEN = db_token('dbcan', config=config)

rule all:
    input:
        PRODIGAL_TOKEN,
        PFAM_TOKEN,
        COG_TOKEN,
        KOFAM_TOKEN,
        UNIOP_TOKEN,
        DBCAN_TOKEN


rule run_prodigal:
    """prodigal"""
    input:
        INPUT_FASTA
    output:
        gff=PRODIGAL_GFF,
        faa=PRODIGAL_FAA
    group: "prodigal"
    threads: rc('prodigal.threads', 1, config=config)
    resources:
        mem_mb=rc('prodigal.mem_mb', 2048, config=config),
        runtime=rc('prodigal.runtime', 30, config=config)
    container: "~/.cache/bioinformatics-tools/prodigal.sif"
    shell:
        """
        prodigal -i {input} -f gff -o {output.gff} -a {output.faa}
        """


rule load_prodigal_to_db:
    """Load prodigal GFF output into SQLite database"""
    input:
        gff=PRODIGAL_GFF
    output:
        tkn=PRODIGAL_TOKEN
    group: "prodigal"
    params:
        db=MAIN_DATABASE,
        script=LOAD_SCRIPT
    shell:
        """
        python {params.script} gff {input.gff} {params.db} prodigal --token {output.tkn}
        """


rule run_pfam:
    input:
        PRODIGAL_FAA
    output:
        PFAM_TSV
    group: "pfam"
    container: "~/.cache/bioinformatics-tools/pfam_scan_light.sif"
    threads: rc('pfam.threads', 4, config=config)
    resources:
        mem_mb=rc('pfam.mem_mb', 4000, config=config),
        runtime=rc('pfam.runtime', 240, config=config)
    params:
        db=rc('pfam.db', "/depot/lindems/data/Databases/pfam", config=config)
    shell:
        """
        pfam_scan.py {input} {params.db} -out {output} -cpu {threads}
        """


rule load_pfam_to_db:
    """Load pfam CSV output into SQLite database"""
    input:
        csv=PFAM_TSV
    output:
        tkn=PFAM_TOKEN
    group: "pfam"
    params:
        db=MAIN_DATABASE,
        script=LOAD_SCRIPT
    shell:
        """
        python {params.script} csv {input.csv} {params.db} pfam --token {output.tkn}
        """


rule run_cog:
    """COGclassifier - classify proteins into COG functional categories"""
    input:
        faa=PRODIGAL_FAA
    output:
        classify=COG_CLASSIFY,
        counts=COG_COUNTS,
        tkn=COG_TKN
    group: "cog"
    params:
        outdir=rc('cog.outdir', 'cog', config=config),
        db=rc('cog.db', '/depot/lindems/data/Databases/cog/', config=config)
    threads: rc('cog.threads', 4, config=config)
    resources:
        mem_mb=rc('cog.mem_mb', 8192, config=config),
        runtime=rc('cog.runtime', 120, config=config)
    container: "~/.cache/bioinformatics-tools/cogclassifier.sif"
    shell:
        """
        LOCAL_DB=$TMPDIR/cog_db
        cp -r {params.db} "$LOCAL_DB"
        COGclassifier -i {input.faa} -o {params.outdir} -d "$LOCAL_DB" -t {threads} \
        && touch {output.tkn}
        """


rule load_cog_to_db:
    """Load COGclassifier TSV output into SQLite database"""
    input:
        classify=COG_CLASSIFY,
        counts=COG_COUNTS
    output:
        tkn=COG_TOKEN
    group: "cog"
    params:
        db=MAIN_DATABASE,
        script=LOAD_SCRIPT
    shell:
        """
        python {params.script} tsv {input.classify} {params.db} cog_classify --token {output.tkn} \
        && python {params.script} tsv {input.counts} {params.db} cog_count
        """


rule run_kofam:
    input:
        faa=PRODIGAL_FAA
    output:
        results=KOFAM_TSV
    container: "~/.cache/bioinformatics-tools/kofam_scan_light_bsp.sif"
    threads: rc('kofam.threads', 16, config=config)
    resources:
        mem_mb=rc('kofam.mem_mb', 4000, config=config),
        runtime=rc('kofam.runtime', 180, config=config)
    group: "kofam"
    params:
        profile_db=rc('kofam.profile_db', "/depot/lindems/data/Databases/kofams/profiles", config=config),
        ko_list=rc('kofam.ko_list', "/depot/lindems/data/Databases/kofams/ko_list", config=config)
    shell:
        """
        exec_annotation {input.faa} -o {output.results} --profile {params.profile_db} --ko-list {params.ko_list} \
        --cpu {threads} --format detail-tsv
        """

rule load_kofam_to_db:
    """Load KOFam_Scan output into SQLite database"""
    input:
        results=KOFAM_TSV
    output:
        tkn=KOFAM_TOKEN
    group: "kofam"
    params:
        db=MAIN_DATABASE,
        script=LOAD_SCRIPT
    shell:
        """
        python {params.script} tsv {input.results} {params.db} kofam_scan --token {output.tkn}
        """


rule run_uniop:
    """Operon prediction using operon_exec"""
    input:
        faa=PRODIGAL_FAA
    output:
        operons=UNIOP_OPERONS
    group: "uniop"
    threads: rc('uniop.threads', 4, config=config)
    resources:
        mem_mb=rc('uniop.mem_mb', 4000, config=config),
        runtime=rc('uniop.runtime', 120, config=config)
    params:
        output_dir=rc('uniop.output_dir', 'uniop', config=config)
    container: "~/.cache/bioinformatics-tools/opr-dev.sif"
    shell:
        """
        operon_exec -i {input.faa} -o {params.output_dir}
        cp $(find {params.output_dir} -name "operons.tsv") {output.operons}
        """


rule load_uniop_to_db:
    """Load operon prediction results into SQLite database"""
    input:
        operons=UNIOP_OPERONS
    output:
        tkn=UNIOP_TOKEN
    group: "uniop"
    params:
        db=MAIN_DATABASE,
        script=LOAD_SCRIPT
    shell:
        """
        python {params.script} tsv {input.operons} {params.db} uniop --token {output.tkn}
        """


rule run_dbcan:
    """dbCAN - CAZyme annotation and CGC prediction"""
    input:
        fasta=INPUT_FASTA
    output:
        overview=DBCAN_OVERVIEW
    group: "dbcan"
    threads: rc('dbcan.threads', 4, config=config)
    resources:
        mem_mb=rc('dbcan.mem_mb', 7984, config=config),
        runtime=rc('dbcan.runtime', 180, config=config)
    params:
        output_dir=rc('dbcan.output_dir', 'dbcan', config=config),
        db=rc('dbcan.db', "/depot/lindems/data/Databases/cazyme/db", config=config)
    container: "~/.cache/bioinformatics-tools/run_dbcan_light.sif"
    shell:
        """
        run_dbcan easy_CGC -v --mode prok --output_dir {params.output_dir} \
        --input_raw_data {input.fasta} --threads {threads} \
        --prokaryotic --db_dir {params.db}
        """


rule load_dbcan_to_db:
    """Load dbCAN overview results into SQLite database"""
    input:
        overview=DBCAN_OVERVIEW
    output:
        tkn=DBCAN_TOKEN
    group: "dbcan"
    params:
        db=MAIN_DATABASE,
        script=LOAD_SCRIPT
    shell:
        """
        python {params.script} tsv {input.overview} {params.db} dbcan --token {output.tkn}
        """

# ═════════════════════════════════════════════════════════════════════════════
#                           NEW RULE TEMPLATE
# ═════════════════════════════════════════════════════════════════════════════
#
# Quick guide for adding new annotation tools to the MARGIE workflow.
#
# STEP 1: Add path definitions at top (around line 15)
# ────────────────────────────────────────────────────────────────────────────
# MYTOOL_OUTPUT = fixed_path('mytool/results.tsv', config=config)
# MYTOOL_TOKEN = db_token('mytool', config=config)
#
# STEP 2: Add token to rule all (around line 53)
# ────────────────────────────────────────────────────────────────────────────
# rule all:
#     input:
#         ...,
#         MYTOOL_TOKEN
#
# STEP 3: Copy and customize this template
# ────────────────────────────────────────────────────────────────────────────
#
# rule run_MYTOOL:
#     """Brief description of what MYTOOL does"""
#     input:
#         PRODIGAL_FAA  # Or INPUT_FASTA if tool needs raw genome
#     output:
#         MYTOOL_OUTPUT
#     group: "MYTOOL"
#     threads: rc('MYTOOL.threads', 4, config=config)
#     resources:
#         mem_mb=rc('MYTOOL.mem_mb', 4000, config=config),
#         runtime=rc('MYTOOL.runtime', 120, config=config)
#     params:
#         db=rc('MYTOOL.db', "/path/to/database", config=config)
#     container: "~/.cache/bioinformatics-tools/MYTOOL.sif"
#     shell:
#         """
#         mytool_command {input} {output} --db {params.db} --threads {threads}
#         """
#
#
# rule load_MYTOOL_to_db:
#     """Load MYTOOL results into SQLite database"""
#     input:
#         MYTOOL_OUTPUT
#     output:
#         tkn=MYTOOL_TOKEN
#     group: "MYTOOL"
#     params:
#         db=MAIN_DATABASE,
#         script=LOAD_SCRIPT
#     shell:
#         """
#         python {params.script} tsv {input} {params.db} MYTOOL --token {output.tkn}
#         """
#
# ─────────────────────────────────────────────────────────────────────────────
# NOTES:
# ─────────────────────────────────────────────────────────────────────────────
# • Use fixed_path() for tools that output to fixed filenames
# • Use build_filepath() for tools where output name can be configured
# • Common inputs: PRODIGAL_FAA (proteins), PRODIGAL_GFF (genes), INPUT_FASTA (raw genome)
# • Always use rc() for configurable parameters with sensible defaults
# • Group name should match tool name for easier debugging
# • loader format: tsv, csv, gff (see load_to_db.py for supported formats)
# ═════════════════════════════════════════════════════════════════════════════