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
        # config.get('out_pfam'),


rule run_prodigal:
    """prodigal"""
    input:
        config.get('input_fasta', '/scratch/negishi/ddeemer/margie/genomes')
    output:
        config.get('out_prodigal', '/scratch/negishi/ddeemer/margie/annotations/prodigal.tkn')
    threads: config.get('prodigal_threads', 1)
    resources:
        mem_mb=2048
        # mem_mb=lambda wc, input: max(2.5 * input.size_mb, 300)
    container: "~/.cache/bioinformatics-tools/prodigal.sif"  # TODO: Need to download if not there
    shell:
        """
        prodigal -i {input} -f gff -o {output}
        """


rule load_prodigal_to_db:
    """Load prodigal GFF output into SQLite database"""
    input:
        gff=config.get('out_prodigal', '/scratch/negishi/ddeemer/margie/annotations/prodigal.tkn')
    output:
        tkn=config.get('out_prodigal_db', 'prodigal_db.tkn')
    params:
        db=config.get('annotations_db', 'annotations.db'),
        script=os.path.join(WORKFLOW_DIR, "load_to_db.py")
    shell:
        """
        python {params.script} {input.gff} {params.db} prodigal --token {output.tkn}
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


rule run_pfam:
    input:
        config.get('input_fasta', './smallish.fasta')
    output:
        config.get('out_pfam', './smallish-pfam.out')
    container: "~/.cache/bioinformatics-tools/pfam_scan_light.sif"
    threads: 4
    params:
        db="/depot/lindems/data/Databases/pfam"
    shell:
        """
        pfam_scan.py {input} {params.db} -out {output} -cpu {threads}
        """


rule run_cog:
    '''requires a protein input file'''
    input:
        "{sample}.faa"
    params:
        outdir="/path/to/output/",
        db="/depot/lindems/data/Databases/cog/"
    output:
        "{sample}.out"
    container: "~/.cache/bioinformatics-tools/cogclassifier.sif"
    shell:
        """
        COGclassifier --infile {input} --outdir {params.outdir} --download_dir {params.db}
        """


rule run_merops:
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
    '''TBD - Not sure'''
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
    '''TBD - Not sure'''
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
    '''TBD - Not sure'''
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
    '''Promoter prediction in bacterial genomes
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
