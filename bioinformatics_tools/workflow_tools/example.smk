"""
Simple 2-rule workflow demonstrating container execution.
"""


print(f"DEBUG: Full config dict: {config}")
print(f"DEBUG: input_fasta = {config.get('input_fasta', 'NOT_SET')}")
print(f"DEBUG: output_fasta = {config.get('output_fasta', 'NOT_SET')}")


rule all:
    input:
        "results/done.txt"


rule run_prodigal_container:
    """Run prodigal with snakemake containerization"""
    input:
        config.get('input_fasta', 'poopballs.fasta')
    output:
        config.get('output_fasta', 'poopydiapy.out')
    threads: config.get('prodigal_threads', 1)
    container: "~/.cache/bioinformatics-tools/prodigal.sif"  # TODO: Need to download if not there
    shell:
        """
        prodigal -h & touch {output}
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
