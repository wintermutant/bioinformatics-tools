"""
Central registry of all available workflows.

Defines all Snakemake workflows that can be executed via the dane_wf CLI.
Each workflow is registered as a WorkflowKey with metadata for execution,
frontend display, and configuration.
"""
from bioinformatics_tools.workflow_tools.models import WorkflowKey


# System-wide required parameters for cluster execution
# These are needed for ANY workflow running via SLURM, not workflow-specific
REQUIRED_SYSTEM_PARAMS = [
    {
        'param': 'compute.cluster-default.account',
        'default': None,
        'description': 'SLURM account for job submission (REQUIRED for cluster execution)',
        'type': 'string',
        'required': True
    },
    {
        'param': 'compute.cluster-default.partition',
        'default': 'cpu',
        'description': 'SLURM partition/queue for job submission',
        'type': 'string'
    },
    {
        'param': 'compute.cluster-default.default_runtime',
        'default': 30,
        'description': 'Default runtime limit in minutes for SLURM jobs',
        'type': 'int'
    },
    {
        'param': 'compute.cluster-default.default_mem_mb',
        'default': 4000,
        'description': 'Default memory limit in MB for SLURM jobs',
        'type': 'int'
    },
    {
        'param': 'compute.cluster-default.max_jobs',
        'default': 5,
        'description': 'Maximum number of concurrent SLURM jobs',
        'type': 'int'
    },
]


WORKFLOWS: dict[str, WorkflowKey] = {
    'example': WorkflowKey(
        cmd_identifier='example',
        snakemake_file='example.smk',
        other=[''],
        sif_files=[
            ('prodigal.sif', '2.6.3-v1.0'),
        ],
        label='Example',
        description='Simple test workflow for development',
        full_description='A minimal workflow for testing the pipeline infrastructure.',
    ),
    'margie': WorkflowKey(
        cmd_identifier='margie',
        snakemake_file='margie.smk',
        other=[''],
        sif_files=[
            ('prodigal.sif', '2.6.3-v1.0'),
            ('pfam_scan_light', 'latest'),
            ('cogclassifier', 'latest')
        ],
        label='Margie',
        description='Full annotation pipeline (Prodigal, Pfam, COG)',
        full_description='Comprehensive microbial genome annotation workflow that combines gene prediction with functional annotation. Runs Prodigal for open reading frame prediction, Pfam for protein family identification, and COGclassifier for functional categorization. Results are automatically loaded into a SQLite database for downstream analysis.',
        tools=[
            {
                'name': 'Prodigal',
                'purpose': 'Gene prediction and ORF identification',
                'version': '2.6.3',
                'output': 'GFF3 file with predicted genes and protein sequences (FAA)'
            },
            {
                'name': 'Pfam_scan',
                'purpose': 'Protein family and domain annotation',
                'version': 'latest',
                'output': 'CSV file with Pfam domain hits'
            },
            {
                'name': 'COGclassifier',
                'purpose': 'Functional categorization using COG database',
                'version': 'latest',
                'output': 'TSV files with COG classifications and category counts'
            }
        ],
        configurable_params=[
            # Prodigal configuration (rule run_prodigal)
            {
                'param': 'prodigal.threads',
                'default': 1,
                'description': 'Number of threads for Prodigal',
                'type': 'int'
            },
            {
                'param': 'prodigal.mem_mb',
                'default': 2048,
                'description': 'Memory limit in MB for Prodigal',
                'type': 'int'
            },
            {
                'param': 'prodigal.runtime',
                'default': 30,
                'description': 'Runtime limit in minutes for Prodigal',
                'type': 'int'
            },
            # Pfam configuration (rule run_pfam)
            {
                'param': 'pfam.threads',
                'default': 4,
                'description': 'Number of threads for Pfam scan',
                'type': 'int'
            },
            {
                'param': 'pfam.mem_mb',
                'default': 4000,
                'description': 'Memory limit in MB for Pfam scan',
                'type': 'int'
            },
            {
                'param': 'pfam.runtime',
                'default': 240,
                'description': 'Runtime limit in minutes for Pfam scan',
                'type': 'int'
            },
            {
                'param': 'pfam.db',
                'default': '/depot/lindems/data/Databases/pfam',
                'description': 'Path to Pfam-A HMM database',
                'type': 'path'
            },
            # COG configuration (rule run_cog)
            {
                'param': 'cog.threads',
                'default': 4,
                'description': 'Number of threads for COGclassifier',
                'type': 'int'
            },
            {
                'param': 'cog.mem_mb',
                'default': 8192,
                'description': 'Memory limit in MB for COGclassifier',
                'type': 'int'
            },
            {
                'param': 'cog.runtime',
                'default': 120,
                'description': 'Runtime limit in minutes for COGclassifier',
                'type': 'int'
            },
            {
                'param': 'cog.db',
                'default': '/depot/lindems/data/Databases/cog/',
                'description': 'Path to COG database directory',
                'type': 'path'
            },
            {
                'param': 'cog.outdir',
                'default': 'cog',
                'description': 'Output directory for COG results',
                'type': 'string'
            }
        ],
        database_deps=[
            'Pfam-A HMM profiles',
            'COG functional database',
            'SQLite results database'
        ],
        docs_url=None
    ),
    'selftest': WorkflowKey(
        cmd_identifier='selftest',
        snakemake_file='selftest.smk',
        other=[''],
        sif_files=[],
        label='Self Test',
        description='Quick validation test (no containers)',
        full_description='Lightweight test workflow that validates SSH, Snakemake, and database caching without using containers. Useful for verifying the pipeline infrastructure is working correctly.',
    ),
}


def get_workflow(name: str) -> WorkflowKey | None:
    """
    Get a workflow definition by name.

    Args:
        name: The workflow identifier (e.g., 'margie', 'example')

    Returns:
        WorkflowKey if found, None otherwise
    """
    return WORKFLOWS.get(name)


def list_workflows() -> list[str]:
    """
    List all registered workflow names.

    Returns:
        List of workflow identifiers
    """
    return list(WORKFLOWS.keys())
