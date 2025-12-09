"""
Simple 3-rule workflow demonstrating container execution.

Usage:
    snakemake --cores 1
"""

# Input file
SAMPLE = "test_data/example"

rule all:
    input:
        "results/done.txt"

rule run_main:
    """Run main.py with the python-example container"""
    input:
        fasta="{sample}.fasta"
    output:
        "results/{sample}_main.txt"
    shell:
        """
        python main.py python-example Dane > {output}
        echo "Processed {input.fasta}" >> {output}
        """

rule run_prodigal:
    """Run prodigal version check"""
    input:
        "results/{sample}_main.txt"
    output:
        "results/{sample}_prodigal.txt"
    shell:
        """
        apptainer.lima exec prodigal.sif prodigal --version > {output} 2>&1
        echo "Input from previous step: {input}" >> {output}
        """

rule run_prodigal_container:
    """Run prodigal with snakemake containerization"""
    input:
        f"{workflow.basedir}/example.fasta"
    output:
        "example-output.txt"
    container: "~/.cache/bioinformatics-tools/prodigal.sif"  # issue here
    shell:
        """
        prodigal --version & touch {output}
        """


rule final_report:
    """Final Python script to say 'all done!'"""
    input:
        "results/{sample}_prodigal.txt"
    output:
        "results/done.txt"
    shell:
        """
        python -c "print('All done! Pipeline completed successfully.')" > {output}
        echo "Processed: {input}" >> {output}
        """
