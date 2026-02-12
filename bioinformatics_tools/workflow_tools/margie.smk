"""
All MARGIE rules. No games.
"""
import os

WORKFLOW_DIR = os.path.dirname(workflow.snakefile)

rule all:
    input:
        config.get('out_prodigal_db', 'prodigal_db.tkn'),
        # config.get('out_dbcan'),
        # config.get('out_kofam'),
        # config.get('out_pfam')
        config.get('out_pfam_db', 'pfam_db.tkn'),
        config.get('out_cog_db', 'cog_db.tkn'),



rule run_prodigal:
    """prodigal"""
    input:
        config.get('input_fasta', '/home/ddeemer/smallish.fasta')
    output:
        gff=config.get('out_prodigal', 'prodigal/prodigal.tkn'),
        faa=config.get('out_prodigal_faa', 'prodigal/prodigal.faa')
    group: "prodigal"
    threads: config.get('prodigal_threads', 1)
    resources:
        mem_mb=2048
        # mem_mb=lambda wc, input: max(2.5 * input.size_mb, 300)
    container: "~/.cache/bioinformatics-tools/prodigal.sif"  # TODO: Need to download if not there
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
        db=config.get('margie_db', '/depot/lindems/data/margie/margie.db'),
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
    threads: 4
    params:
        db=config.get("pfam_db", "/depot/lindems/data/Databases/pfam")
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
        db=config.get('margie_db', 'margie.db'),
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} csv {input.csv} {params.db} pfam --token {output.tkn}
        """


rule run_cog:
    """COGclassifier - classify proteins into COG functional categories"""
    input:
        faa=config.get('out_prodigal_faa', '/home/ddeemer/smallish.faa')
    output:
        classify=config.get('out_cog_classify', 'cog/cog_classify.tsv'),
        counts=config.get('out_cog_count', 'cog/cog_count.tsv'),
        tkn=config.get('out_cog', 'cog/cog.tkn')
    group: "cog"
    params:
        outdir=config.get('cog_outdir', 'cog'),
        db=config.get('cog_db', '/depot/lindems/data/Databases/cog/')
    threads: config.get('cog_threads', 4)
    resources:
        mem_mb=8192
    container: "~/.cache/bioinformatics-tools/cogclassifier.sif"
    shell:
        """
        COGclassifier -i {input.faa} -o {params.outdir} -d {params.db} -t {threads} \
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
        db=config.get('margie_db', 'margie.db'),
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} tsv {input.classify} {params.db} cog_classify --token {output.tkn} \
        && python {params.script} tsv {input.counts} {params.db} cog_count
        """


rule run_dbcan:
    input:
        config.get('input_fasta', '/depot/lindems/data/Database/example-data/small.fasta')
    output:
        tkn = config.get('out_dbcan', '/depot/lindems/data/Database/example-output/small-dbcan.out')
    threads: 4
    resources:
        mem_mb=7984
    params:
        db="/depot/lindems/data/Databases/cazyme/db"
    container: "~/.cache/bioinformatics-tools/run_dbcan_light.sif"
    shell:
        """
        run_dbcan easy_CGC -v --mode prok --output_dir . --input_raw_data {input} --threads {threads} \
        --prokaryotic --db_dir {params.db} && touch {output}
        """


rule run_kofam:
    input:
        config.get('input_fasta', './smallish.fasta')
    output:
        config.get('out_kofam', './smallish-kofam.out')
    container: "~/.cache/bioinformatics-tools/kofam_scan_light.sif"
    threads: 8
    params:
        profile_db="/depot/lindems/data/Databases/kofams/profiles",
        ko_list="/depot/lindems/data/Databases/kofams/ko_list"
    shell:
        """
        exec_annotation {input} -o {output} --profile {params.profile_db} --ko-list {params.ko_list} \
        --cpu {threads} --format detail-tsv
        """


rule run_merops:
    '''TODO: INCOMPLETE'''
    input:
        "{sample}.fasta"
    output:
        "{sample}.out"
    params:
        db="/depot/lindems/data/Databases/merops/merops.dmnd"
    container: "~/.cache/bioinformatics-tools/diamond.sif"
    shell:
        """
        diamond blastx -d {db} -q {input.fasta} -o {output}
        """


rule run_tigr:
    '''TODO: INCOMPLETE'''
    input:
        "{sample}.faa"
    output:
        one="Annotations/TigrFamResults/{sample}.hmmer.TIGR.hmm",
        two="Annotations/TigrFamResults/{sample}.hmmer.TIGR.tbl"
    params:
        db="/depot/lindems/data/Databases/tigrfams/hmm_PGAP.LIB"
    container: "~/.cache/bioinformatics-tools/hmmer.sif"
    threads: 4
    shell:
        """
        hmmscan -o {output.one} --tblout {output.two} --cpu {threads} {params.db} {input}
        """


rule run_uniport:
    '''TODO: INCOMPLETE'''
    input:
        "{sample}.fasta"
    output:
        "{sample}.out"
    params:
        db="/depot/lindems/data/Databases/uniref/uniref90"
    # container: "~/.cache/"
    shell:
        """
        touch {output}
        """

rule term_predict:
    '''TODO: INCOMPLETE'''
    input:
        "{sample}.fasta"
    output:
        "{sample}.out"
    # container: "~/.cache/"
    shell:
        """
        touch {output}
        """

rule run_rast:
    '''TODO: INCOMPLETE'''
    input:
        "{sample}.fasta"
    output:
        "{sample}.out"
    # container: "~/.cache/"
    shell:
        """
        touch {output}
        """


rule run_tcdb:
    '''TODO: INCOMPLETE'''
    input:
        "{sample}.fasta"
    output:
        "{sample}.out"
    # container: "~/.cache/"
    shell:
        """
        touch {output}
        """


rule run_promotech:
    '''
    TODO: INCOMPLETE
    Promoter prediction in bacterial genomes
    https://github.com/BioinformaticsLabAtMUN/Promotech
    '''
    input:
        "{sample}.fasta"
    output:
        "{sample}.out"
    # container: "~/.cache/"
    shell:
        """
        touch {output}
        """


rule run_template:
    '''TODO: INCOMPLETE'''
    input:
        "{sample}.fasta"
    output:
        "{sample}.out"
    # container: "~/.cache/"
    shell:
        """
        touch {output}
        """


rule finalize:
    """Create done file from prodigal output"""
    input:
        config.get('output_fasta', 'poopydiapy.out')
    output:
        "results/done.txt"
    shell:
        """
        mkdir -p results
        echo "Workflow completed! Input processed: {input}" > {output}
        cat {input} >> {output}
        """
