"""
All MARGIE rules. No games.
"""

rule all:
    input:
        config.get('out_prodigal'),
        config.get('out_dbcan'),
        config.get('out_kofam')


rule run_prodigal:
    """prodigal"""
    input:
        config.get('input_fasta', '/scratch/negishi/ddeemer/margie/genomes')
    output:
        config.get('out_prodigal', '/scratch/negishi/ddeemer/margie/annotations/prodigal.tkn')
    threads: config.get('prodigal_threads', 1)
    resources:
        mem_mb=100
        # mem_mb=lambda wc, input: max(2.5 * input.size_mb, 300)
    container: "~/.cache/bioinformatics-tools/prodigal.sif"  # TODO: Need to download if not there
    shell:
        """
        prodigal -i {input} -o {output}
        touch {output}
        """


rule run_dbcan:
    input:
        config.get('input_fasta', '/depot/lindems/data/Database/example-data/small.fasta')
    output:
        config.get('out_dbcan', '/depot/lindems/data/Database/example-output/small-dbcan.out')
    threads: 16
    params:
        db="/depot/lindems/data/Databases/cazyme-2026/db"
    container: "~/.cache/bioinformatics-tools/run_dbcan_light.sif"
    shell:
        """
        run_dbcan easy_CGC -v --mode prok --output_dir $(dirname {output}) --input_raw_data {input} --threads {threads} \
        --prokaryotic --db_dir {params.db}
        touch {output}
        """


rule run_kofam:
    input:
        config.get('input_fasta', '/depot/lindems/data/Database/example-data/small.fasta')
    output:
        config.get('out_kofam', '/depot/lindems/data/Database/example-output/small-kofam.out')
    container: "~/.cache/bioinformatics-tools/kofam_scan_light.sif"
    threads: 4
    params:
        profile_db="/depot/lindems/data/Databases/KOFams/profiles",
        ko_list="/depot/lindems/data/Databases/KOFams/ko_list"
    shell:
        """
        exec_annotation {input} -o {output} --profile {params.profile_db} --ko-list {params.ko_list} \
        --cpu {threads}
        touch {output}
        """


rule run_pfam:
    input:
        config.get('input_fasta', '/depot/lindems/data/Database/example-data/small.fasta')
    output:
        config.get('out_pfam', '/depot/lindems/data/Database/example-output/small-pfam.out')
    container: "~/.cache/bioinformatics-tools/pfam_scan_light.sif"
    threads: 4
    params:
        db="/depot/lindems/data/Databases/Pfam"
    shell:
        """
        pfam_scan.py {input} {params.db} -out {output} -cpu {threads}
        """



rule run_cog:
    input:
        "{sample}.fasta"
    output:
        "{sample}.out"
    # container: "~/.cache/"
    shell:
        """
        touch {output}
        """


rule run_meropes:
    input:
        "{sample}.fasta"
    output:
        "{sample}.out"
    # container: "~/.cache/"
    shell:
        """
        touch {output}
        """


rule run_tigr:
    input:
        "{sample}.fasta"
    output:
        "{sample}.out"
    # container: "~/.cache/"
    shell:
        """
        touch {output}
        """


rule run_uniport:
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
