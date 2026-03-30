"""
All MARGIE rules. No games.
"""
import os
import sys

# Add current directory to path to import workflow_helpers
sys.path.insert(0, os.path.dirname(workflow.snakefile))
from workflow_helpers import rc, fixed_path, tool_output, db_token

WORKFLOW_DIR = os.path.dirname(workflow.snakefile)

rule all:
    input:
        db_token('prodigal', config=config),
        db_token('pfam', config=config),
        db_token('cog', config=config),
        db_token('kofam', config=config),
        db_token('uniop', config=config),
        db_token('dbcan', config=config)


rule run_prodigal:
    """prodigal"""
    input:
        rc('input_fasta', config=config)
    output:
        gff=tool_output('prodigal.output', 'gff', config=config),
        faa=tool_output('prodigal.output', 'faa', config=config)
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
        gff=tool_output('prodigal.output', 'gff', config=config)
    output:
        tkn=db_token('prodigal', config=config)
    group: "prodigal"
    params:
        db=rc('main_database', config=config),  # TODO: Add specific error if main_database is not set
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} gff {input.gff} {params.db} prodigal --token {output.tkn}
        """


rule run_pfam:
    input:
        tool_output('prodigal.output', 'faa', config=config)
    output:
        fixed_path('pfam', 'pfam.tsv', use_stem=False, config=config)
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
        csv=fixed_path('pfam', 'pfam.tsv', use_stem=False, config=config)
    output:
        tkn=db_token('pfam', config=config)
    group: "pfam"
    params:
        db=rc('main_database', config=config),  # TODO: Add specific error if main_database is not set
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} csv {input.csv} {params.db} pfam --token {output.tkn}
        """


rule run_cog:
    """COGclassifier - classify proteins into COG functional categories"""
    input:
        faa=tool_output('prodigal.output', 'faa', config=config)
    output:
        classify=fixed_path('cog', 'cog_classify.tsv', use_stem=False, config=config),
        counts=fixed_path('cog', 'cog_count.tsv', use_stem=False, config=config),
        tkn=fixed_path('cog', 'cog.tkn', use_stem=False, config=config)
    group: "cog"
    params:
        outdir=rc('cog.outdir', 'cog', config=config),
        db=rc('cog.db', '/depot/lindems/data/Databases/cog/', config=config)
    threads: rc('cog.threads', 4, config=config)
    resources:
        mem_mb=rc('cog.mem_mb', 8192, config=config),
        runtime=rc('cog.runtime', 120, config=config)
    container: "~/.cache/bioinformatics-tools/cogclassifier.sif"
    shell:  # TODO: Remove this copy command
        """
        LOCAL_DB=$TMPDIR/cog_db
        cp -r {params.db} "$LOCAL_DB"
        COGclassifier -i {input.faa} -o {params.outdir} -d "$LOCAL_DB" -t {threads} \
        && touch {output.tkn}
        """


rule load_cog_to_db:
    """Load COGclassifier TSV output into SQLite database"""
    input:
        classify=fixed_path('cog', 'cog_classify.tsv', use_stem=False, config=config),
        counts=fixed_path('cog', 'cog_count.tsv', use_stem=False, config=config)
    output:
        tkn=db_token('cog', config=config)
    group: "cog"
    params:
        db=rc('main_database', config=config),  # TODO: Add specific error if main_database is not set
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} tsv {input.classify} {params.db} cog_classify --token {output.tkn} \
        && python {params.script} tsv {input.counts} {params.db} cog_count
        """


rule run_kofam:
    input:
        faa=tool_output('prodigal.output', 'faa', config=config)
    output:
        results=fixed_path('kofam', 'kofam.tsv', use_stem=False, config=config)
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
        results=fixed_path('kofam', 'kofam.tsv', use_stem=False, config=config)
    output:
        tkn=db_token('kofam', config=config)
    group: "kofam"
    params:
        db=rc('main_database', config=config),  # TODO: Add specific error if main_database is not set
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} tsv {input.results} {params.db} kofam_scan --token {output.tkn}
        """


rule run_uniop:
    """Operon prediction using operon_exec"""
    input:
        faa=tool_output('prodigal.output', 'faa', config=config)
    output:
        operons=fixed_path('uniop', 'operons.tsv', use_stem=False, config=config)
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
        operons=fixed_path('uniop', 'operons.tsv', use_stem=False, config=config)
    output:
        tkn=db_token('uniop', config=config)
    group: "uniop"
    params:
        db=rc('main_database', config=config),  # TODO: Add specific error if main_database is not set
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} tsv {input.operons} {params.db} uniop --token {output.tkn}
        """


rule run_dbcan:
    """dbCAN - CAZyme annotation and CGC prediction"""
    input:
        fasta=rc('input_fasta', config=config)
    output:
        overview=fixed_path('dbcan', 'overview.tsv', use_stem=False, config=config)
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
        overview=fixed_path('dbcan', 'overview.tsv', use_stem=False, config=config)
    output:
        tkn=db_token('dbcan', config=config)
    group: "dbcan"
    params:
        db=rc('main_database', config=config),  # TODO: Add specific error if main_database is not set
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} tsv {input.overview} {params.db} dbcan --token {output.tkn}
        """

# Rules to add
# rule run_merops:
# rule run_tigr:
# rule run_uniport:
# rule term_predict:
# rule run_rast:
# rule run_tcdb:
# rule run_promotech:
# rule finalize: