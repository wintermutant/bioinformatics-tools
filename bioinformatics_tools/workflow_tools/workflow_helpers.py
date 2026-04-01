"""
Shared utilities for Snakemake workflows.

Provides configuration helpers and standardized path generation.
Import into Snakemake files to access config and generate output paths.
"""
from pathlib import Path


def rc(key: str, default:str|None = None, config=None):
    """
    Rule Config: Get config value using dot notation for nested keys.

    Supports arbitrary nesting via dot notation:
    key: Config key using dot notation (e.g., 'prodigal.mem_mb')

    Returns:
        The config value OR default OR if not set
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


def get_input_stem(config):
    """
    Extract stem (filename without extension) from input file.
    """
    input_file = config.get('input_fasta', 'output')
    return Path(input_file).stem


def get_workflow_prefix(config) -> str | Path:
    """
    Get output directory prefix with stem subdirectory and trailing slash.

    Each genome gets isolated in its own subdirectory for clean batch processing.

    Example:
        input_fasta: 'ecoli.fasta'
        output_dir: '/results/batch-run'
        → '/results/batch-run/ecoli/'
    """
    output_dir = config.get('output_dir', '')
    if not output_dir:
        return ''

    stem = get_input_stem(config)
    abs_path = Path(output_dir).resolve()
    return f"{abs_path}/{stem}/"


def fixed_path(relative_path: str, config=None) -> str:
    """Prepend workflow prefix to a relative path. E.g., 'prodigal/file.faa' → 'results/prodigal/file.faa'"""
    if config is None:
        raise ValueError("config parameter is required")

    prefix = get_workflow_prefix(config)
    return f"{prefix}{relative_path}"


def build_filepath(config_string: str, suffix: str, default: str = None, config=None) -> str:
    """
    Build filepath with config lookup and auto-generation.

    Priority: 1) Config value, 2) Default path, 3) Auto-generate {tool}/{stem}-{tool}.{suffix}

    Examples:
        build_filepath('pfam.output', suffix='tsv') → 'results/pfam/ecoli-pfam.tsv'
        build_filepath('cog.output', suffix='txt', default='cog/results.txt') → 'results/cog/results.txt'
        # With config pfam.output='custom.tsv' → 'results/pfam/custom.tsv'
    """
    if config is None:
        raise ValueError("config parameter is required")

    prefix = get_workflow_prefix(config)

    parts = config_string.split('.')
    if len(parts) < 1:
        raise ValueError(f"config_string must have at least one part, got: {config_string}")
    tool = parts[0]

    # Check config first
    config_filename = rc(config_string, None, config=config)
    if config_filename:
        return f"{prefix}{tool}/{config_filename}"

    # Use default if provided
    if default:
        return f"{prefix}{default}"

    # Auto-generate with stem
    stem = get_input_stem(config)
    return f"{prefix}{tool}/{stem}-{tool}.{suffix}"


def db_token(tool, config=None):
    """Generate database token path: {tool}/{tool}_db.tkn"""
    return fixed_path(f'{tool}/{tool}_db.tkn', config=config)
