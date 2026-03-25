"""
All MARGIE rules. No games.
"""
import os

WORKFLOW_DIR = os.path.dirname(workflow.snakefile)

def rc(rule_name, param=None, default=None):
    """
    Rule Config: Get config value for a specific rule's parameter.

    Supports both nested and top-level config patterns:

    Example configs:
        # Nested (for tool parameters)
        prodigal:
          threads: 1
          mem_mb: 2048

        # Top-level (for simple values)
        mykey: value

    Usage in rules:
        threads: rc('prodigal', 'threads', 1)   # nested lookup
        value: rc('mykey', default='fallback')  # top-level lookup

    Args:
        rule_name: The tool name or config key
        param: Parameter name (optional, for nested configs)
        default: Default value if not found in config

    Returns:
        The config value or default if not set
    """
    # Use global config (available in all Snakemake files)
    # This is more reliable than workflow.config during rule definition

    # If param is None, lookup rule_name as a top-level key
    if param is None:
        return config.get(rule_name, default)

    # Try nested lookup: config[rule_name][param]
    rule_config = config.get(rule_name, {})
    if isinstance(rule_config, dict):
        return rule_config.get(param, default)

    return default

rule all:
    input:
        config.get('out_prodigal_db', 'prodigal_db.tkn'),
        config.get('out_pfam_db', 'pfam_db.tkn'),
        config.get('out_cog_db', 'cog_db.tkn'),
        config.get('out_kofam_db', 'kofam/kofam_db.tkn'),
        config.get('out_uniop_db', 'uniop/uniop_db.tkn'),
        config.get('out_dbcan_db', 'dbcan/dbcan_db.tkn')


rule run_prodigal:
    """prodigal"""
    input:
        config.get('input_fasta')
    output:
        gff=config.get('out_prodigal_gff', 'prodigal/prodigal.tkn'),
        faa=config.get('out_prodigal_faa', 'prodigal/prodigal.faa')
    group: "prodigal"
    threads: rc('prodigal', 'threads', 1)
    resources:
        mem_mb=rc('prodigal', 'mem_mb', 2048),
        runtime=rc('prodigal', 'runtime', 30)
    container: "~/.cache/bioinformatics-tools/prodigal.sif"
    shell:
        """
        prodigal -i {input} -f gff -o {output.gff} -a {output.faa}
        """


rule load_prodigal_to_db:
    """Load prodigal GFF output into SQLite database"""
    input:
        gff=config.get('out_prodigal', 'prodigal/prodigal.tkn')
    output:
        tkn=config.get('out_prodigal_db', 'prodigal/prodigal_db.tkn')
    group: "prodigal"
    params:
        db=config['main_database'],  # Required - no fallback
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} gff {input.gff} {params.db} prodigal --token {output.tkn}
        """


rule run_pfam:
    input:
        config.get('out_prodigal_faa', '/home/ddeemer/smallish.faa')
    output:
        config.get('out_pfam', 'pfam/pfam.tkn')
    group: "pfam"
    container: "~/.cache/bioinformatics-tools/pfam_scan_light.sif"
    threads: rc('pfam', 'threads', 4)
    resources:
        mem_mb=rc('pfam', 'mem_mb', 4000),
        runtime=rc('pfam', 'runtime', 240)
    params:
        db=rc('pfam', 'db', "/depot/lindems/data/Databases/pfam")
    shell:
        """
        pfam_scan.py {input} {params.db} -out {output} -cpu {threads}
        """


rule load_pfam_to_db:
    """Load pfam CSV output into SQLite database"""
    input:
        csv=config.get('out_pfam', 'pfam/pfam.tkn')
    output:
        tkn=config.get('out_pfam_db', 'pfam/pfam_db.tkn')
    group: "pfam"
    params:
        db=config['main_database'],  # Required - no fallback
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} csv {input.csv} {params.db} pfam --token {output.tkn}
        """


rule run_cog:
    """COGclassifier - classify proteins into COG functional categories"""
    input:
        faa=config.get('out_prodigal_faa')
    output:
        classify=config.get('out_cog_classify', 'cog/cog_classify.tsv'),
        counts=config.get('out_cog_count', 'cog/cog_count.tsv'),
        tkn=config.get('out_cog', 'cog/cog.tkn')
    group: "cog"
    params:
        outdir=rc('cog', 'outdir', 'cog'),
        db=rc('cog', 'db', '/depot/lindems/data/Databases/cog/')
    threads: rc('cog', 'threads', 4)
    resources:
        mem_mb=rc('cog', 'mem_mb', 8192),
        runtime=rc('cog', 'runtime', 120)
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
        classify=config.get('out_cog_classify', 'cog/cog_classify.tsv'),
        counts=config.get('out_cog_count', 'cog/cog_count.tsv')
    output:
        tkn=config.get('out_cog_db', 'cog/cog_db.tkn')
    group: "cog"
    params:
        db=config['main_database'],  # Required - no fallback
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} tsv {input.classify} {params.db} cog_classify --token {output.tkn} \
        && python {params.script} tsv {input.counts} {params.db} cog_count
        """


rule run_kofam:
    input:
        faa=config.get('out_prodigal_faa')
    output:
        results=config.get('out_kofam', 'kofam/kofam.tkn')
    container: "~/.cache/bioinformatics-tools/kofam_scan_light_bsp.sif"
    threads: rc('kofam', 'threads', 16)
    resources:
        mem_mb=rc('kofam', 'mem_mb', 4000),
        runtime=rc('kofam', 'runtime', 180)
    group: "kofam"
    params:
        profile_db=rc('kofam', 'profile_db', "/depot/lindems/data/Databases/kofams/profiles"),
        ko_list=rc('kofam', 'ko_list', "/depot/lindems/data/Databases/kofams/ko_list")
    shell:
        """
        exec_annotation {input.faa} -o {output.results} --profile {params.profile_db} --ko-list {params.ko_list} \
        --cpu {threads} --format detail-tsv
        """

rule load_kofam_to_db:
    """Load KOFam_Scan output into SQLite database"""
    input:
        results=config.get('out_kofam'),
    output:
        tkn=config.get('out_kofam_db', 'kofam/kofam_db.tkn')
    group: "kofam"
    params:
        db=config['main_database'],  # Required - no fallback
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} tsv {input.results} {params.db} kofam_scan --token {output.tkn}
        """


rule run_uniop:
    """Operon prediction using operon_exec"""
    input:
        faa=config.get('out_prodigal_faa')
    output:
        operons=config.get('out_uniop', 'uniop/operons.tsv')
    group: "uniop"
    threads: rc('uniop', 'threads', 4)
    resources:
        mem_mb=rc('uniop', 'mem_mb', 4000),
        runtime=rc('uniop', 'runtime', 120)
    params:
        output_dir=rc('uniop', 'output_dir', 'uniop')
    container: "~/.cache/bioinformatics-tools/opr-dev.sif"
    shell:
        """
        operon_exec -i {input.faa} -o {params.output_dir}
        find {params.output_dir} -name "operons.tsv" -exec cp {{}} {output.operons} \;
        """


rule load_uniop_to_db:
    """Load operon prediction results into SQLite database"""
    input:
        operons=config.get('out_uniop', 'uniop/operons.tsv')
    output:
        tkn=config.get('out_uniop_db', 'uniop/uniop_db.tkn')
    group: "uniop"
    params:
        db=config['main_database'],  # Required - no fallback
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} tsv {input.operons} {params.db} uniop --token {output.tkn}
        """


rule run_dbcan:
    """dbCAN - CAZyme annotation and CGC prediction"""
    input:
        fasta=rc('input_fasta')
    output:
        overview=config.get('out_dbcan', 'dbcan/overview.tsv')
    group: "dbcan"
    threads: rc('dbcan', 'threads', 4)
    resources:
        mem_mb=rc('dbcan', 'mem_mb', 7984),
        runtime=rc('dbcan', 'runtime', 180)
    params:
        output_dir=rc('dbcan', 'output_dir', 'dbcan'),
        db=rc('dbcan', 'db', "/depot/lindems/data/Databases/cazyme/db")
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
        overview=config.get('out_dbcan', 'dbcan/overview.tsv')
    output:
        tkn=config.get('out_dbcan_db', 'dbcan/dbcan_db.tkn')
    group: "dbcan"
    params:
        db=config['main_database'],  # Required - no fallback
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