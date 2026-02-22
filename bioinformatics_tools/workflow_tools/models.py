from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ApptainerKey:
    '''connecting programs to their respective container needed'''
    executable: Path | str
    sif_path: Path | str
    commands: list[tuple]


@dataclass
class WorkflowKey:
    '''Metadata for a single Snakemake workflow.'''
    cmd_identifier: str
    snakemake_file: str
    other: list[str]
    sif_files: list[tuple] = field(default_factory=list)