"""
Shared utilities for Snakemake workflows.

Provides configuration helpers and standardized path generation.
Import into Snakemake files to access config and generate output paths.
"""
from pathlib import Path


def rc(key, default=None, config=None):
    """
    Rule Config: Get config value using dot notation for nested keys.

    Supports arbitrary nesting via dot notation:

    Example config:
        prodigal:
          threads: 1
          mem_mb: 2048
        compute:
          cluster_default:
            account: myaccount
            partition: cpu

    Usage in rules:
        threads: rc('prodigal.threads', 1, config=config)
        account: rc('compute.cluster_default.account', None, config=config)
        simple: rc('input_fasta', config=config)

    Args:
        key: Config key using dot notation (e.g., 'prodigal.mem_mb')
        default: Default value if not found in config
        config: The Snakemake config dict

    Returns:
        The config value or default if not set
    """
    if config is None:
        raise ValueError("config parameter is required")

    # Split key by dots and traverse nested dict
    parts = key.split('.')
    value = config

    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default

    return value


def get_stem(config):
    """
    Extract stem (filename without extension) from input file.
    """
    input_file = config.get('input_fasta', 'output')
    return Path(input_file).stem


def get_prefix(config):
    """
    Get output directory prefix with trailing slash.
    Always returns an absolute path.

    Example:
        output_dir: './tmp-2'
        --> '/home/ddeemer/git-repos/bioinformatics-tools/tmp-2/'

        output_dir: '/results/2024-03-24'
        --> '/results/2024-03-24/'
    """
    output_dir = config.get('output_dir', '')
    if not output_dir:
        return ''

    # Convert to absolute path and add trailing slash
    abs_path = Path(output_dir).resolve()
    return f"{abs_path}/"


def fixed_path(tool, filename='', use_stem=True, config=None) -> str:
    """
    Generate output paths for fixed filenames (non-configurable).

    Use this for tool outputs with fixed, unchanging filenames like:
    - pfam.tsv (always named 'pfam.tsv')

    For user-configurable outputs, use tool_output() instead.

    Generates paths using the pattern:
        {prefix}{tool}/{stem}-{filename}  (if use_stem=True)
        {prefix}{tool}/{filename}          (if use_stem=False)

    Examples:
        # With stem
        fixed_path('prodigal', 'prodigal.faa', config=config)
        # config: input_fasta='ecoli.fasta', output_dir='results/'
        # 'results/prodigal/ecoli-prodigal.faa'

        # Without stem (fixed filename)
        fixed_path('pfam', 'pfam.tsv', use_stem=False, config=config)
        # 'results/pfam/pfam.tsv'
    """
    if config is None:
        raise ValueError("config parameter is required")

    prefix = get_prefix(config)
    stem = get_stem(config)

    # Build filename
    if use_stem and filename and stem:
        final_filename = f"{stem}-{filename}"
    else:
        final_filename = filename

    return f"{prefix}{tool}/{final_filename}"


def tool_output(config_key, suffix, config=None) -> str:
    """
    Generate standardized output path with support for user-specified filenames.

    CONVENTION: The first part of config_key is ALWAYS the tool/directory name.
    This supports arbitrary nesting while maintaining predictable directory structure.

    Example configs:
        # Simple case
        prodigal:
          output: my_custom_genes

        # Nested case (supports versioning, variants, etc.)
        prodigal:
          version1:
            output: custom_v1
            threads: 4
          version2:
            output: custom_v2

    Usage:
        tool_output('prodigal.output', 'gff', config=config)
        → Directory: 'prodigal/', Lookup: config['prodigal']['output']

        tool_output('prodigal.version1.output', 'gff', config=config)
        → Directory: 'prodigal/', Lookup: config['prodigal']['version1']['output']

    Args:
        config_key: Dot-notation config key where first part = tool/directory name
                   (e.g., 'prodigal.output', 'prodigal.v1.output')
        suffix: File extension (e.g., 'gff', 'faa')
        config: The Snakemake config dict

    Examples:
        # User specifies custom filename (simple)
        # config: prodigal.output = 'my_genes'
        tool_output('prodigal.output', 'gff', config=config)
        → 'results/prodigal/my_genes.gff'

        # User specifies custom filename (nested)
        # config: prodigal.v1.output = 'custom_v1'
        tool_output('prodigal.v1.output', 'gff', config=config)
        → 'results/prodigal/custom_v1.gff'

        # User doesn't specify, auto-generate with stem
        # config: input_fasta = 'ecoli.fasta'
        tool_output('prodigal.output', 'gff', config=config)
        → 'results/prodigal/ecoli-prodigal.gff'
    """
    if config is None:
        raise ValueError("config parameter is required")

    # Parse config_key - FIRST PART is always the tool/directory name
    parts = config_key.split('.')
    if len(parts) < 1:
        raise ValueError(f"config_key must have at least one part, got: {config_key}")

    tool = parts[0]  # First part determines directory structure

    # Check if user specified a custom filename via rc() (supports arbitrary nesting)
    custom_filename = rc(config_key, None, config=config)

    prefix = get_prefix(config)

    if custom_filename:
        # User specified custom filename: {prefix}{tool}/{custom_filename}.{suffix}
        return f"{prefix}{tool}/{custom_filename}.{suffix}"
    else:
        # Auto-generate with stem: {prefix}{tool}/{stem}-{tool}.{suffix}
        stem = get_stem(config)
        return f"{prefix}{tool}/{stem}-{tool}.{suffix}"


def db_token(tool, config=None):
    """
    Generate database token path: {tool}/{stem}-{tool}_db.tkn

    Args:
        tool: Tool name (e.g., 'prodigal', 'pfam')
        config: The Snakemake config dict

    Returns:
        Path to database token file

    Example:
        db_token('prodigal', config=config)
        → 'results/prodigal/ecoli-prodigal_db.tkn'
    """
    return fixed_path(tool, f'{tool}_db.tkn', use_stem=True, config=config)
