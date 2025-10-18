'''
Intelligently batch small files into compressed tarballs to reduce file counts.
Optimized for speed with streaming compression and batched operations.
'''
import os
import tarfile
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

app = typer.Typer(help="Archive small files into tarballs to reduce file counts")
console = Console()

# Compression type mapping
COMPRESSION_MAP = {
    'gz': 'gz',
    'gzip': 'gz',
    'bz2': 'bz2',
    'bzip2': 'bz2',
    'xz': 'xz',
    'none': ''
}


def format_size(size_bytes: int) -> str:
    """Format bytes as human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def collect_files(
    root_path: Path,
    max_file_size_mb: float,
    min_file_size_mb: float,
    exclude_patterns: List[str]
) -> Tuple[List[Tuple[Path, int]], List[Path], int]:
    """
    Quickly collect files to archive and files to skip.

    Returns:
        (files_to_archive, skipped_files, total_count)
        files_to_archive: List of (path, size) tuples
        skipped_files: List of paths that were skipped
    """
    files_to_archive = []
    skipped_files = []
    total_files = 0

    max_bytes = int(max_file_size_mb * 1024 * 1024)
    min_bytes = int(min_file_size_mb * 1024 * 1024)

    # Use os.walk for speed
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Filter out excluded directories
        dirnames[:] = [d for d in dirnames if not any(
            d == pattern or d.startswith(pattern.rstrip('*'))
            for pattern in exclude_patterns
        )]

        for filename in filenames:
            # Skip excluded files
            if any(filename.endswith(pattern[1:]) if pattern.startswith('*') else filename == pattern
                   for pattern in exclude_patterns):
                continue

            # Skip existing archives
            if filename.endswith(('.tar', '.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2')):
                continue

            full_path = Path(dirpath) / filename
            total_files += 1

            try:
                file_size = full_path.stat().st_size

                if file_size < min_bytes:
                    continue  # Too small, skip
                elif file_size > max_bytes:
                    skipped_files.append(full_path)
                else:
                    files_to_archive.append((full_path, file_size))

            except (PermissionError, OSError):
                continue

    return files_to_archive, skipped_files, total_files


def create_archive_batches(
    files: List[Tuple[Path, int]],
    max_archive_size_mb: float,
    root_path: Path
) -> List[List[Tuple[Path, int, str]]]:
    """
    Batch files into archives, including relative paths.

    Returns:
        List of batches, where each batch is [(abs_path, size, rel_path), ...]
    """
    max_archive_bytes = int(max_archive_size_mb * 1024 * 1024)
    batches = []
    current_batch = []
    current_size = 0

    for file_path, file_size in files:
        # Calculate relative path from root
        rel_path = file_path.relative_to(root_path)

        # Check if adding this file would exceed the limit
        if current_size + file_size > max_archive_bytes and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_size = 0

        current_batch.append((file_path, file_size, str(rel_path)))
        current_size += file_size

    # Add the last batch
    if current_batch:
        batches.append(current_batch)

    return batches


def create_tarball(
    batch: List[Tuple[Path, int, str]],
    output_path: Path,
    compression: str
) -> bool:
    """
    Create a tarball from a batch of files.
    Uses streaming for speed.

    Returns:
        True if successful, False otherwise
    """
    try:
        # Determine tar mode
        mode = f'w:{compression}' if compression else 'w'

        with tarfile.open(output_path, mode) as tar:
            for abs_path, _, rel_path in batch:
                try:
                    # Add with relative path as arcname
                    tar.add(abs_path, arcname=rel_path)
                except (PermissionError, OSError) as e:
                    console.print(f"[yellow]Warning: Could not add {abs_path}: {e}[/yellow]")
                    continue

        return True
    except Exception as e:
        console.print(f"[red]Error creating {output_path}: {e}[/red]")
        return False


@app.command()
def main(
    path: Path = typer.Argument(
        ...,
        help="Directory to archive",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True
    ),
    max_file_size: float = typer.Option(
        4096.0,
        "--max-file-size",
        "-M",
        help="Maximum file size in MB to include (larger files skipped)"
    ),
    max_archive_size: float = typer.Option(
        2048.0,
        "--max-archive-size",
        "-m",
        help="Target size in MB for each archive"
    ),
    min_file_size: float = typer.Option(
        0.0,
        "--min-file-size",
        help="Minimum file size in MB to include"
    ),
    compression: str = typer.Option(
        "gz",
        "--compression",
        "-c",
        help="Compression type: gz, bz2, xz, none"
    ),
    delete_originals: bool = typer.Option(
        False,
        "--delete-originals",
        "-d",
        help="Delete original files after successful archiving"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be archived without doing it"
    ),
    exclude: List[str] = typer.Option(
        [],
        "--exclude",
        "-e",
        help="Patterns to exclude (can be used multiple times)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Directory to write archives (default: same as input)"
    ),
):
    """
    Archive small files into tarballs to reduce file counts.

    Recursively walks the directory tree, collects files under --max-file-size,
    and batches them into compressed tarballs while preserving directory structure.

    Examples:
        # Dry run to preview
        misc archive_files /path/to/data --dry-run

        # Archive with defaults
        misc archive_files /path/to/data

        # Archive and delete originals
        misc archive_files /path/to/data --delete-originals

        # Custom settings
        misc archive_files /path/to/data -M 1024 -m 512 -c xz
    """
    # Validate compression type
    if compression not in COMPRESSION_MAP:
        console.print(f"[red]Invalid compression type: {compression}[/red]")
        console.print(f"Valid options: {', '.join(COMPRESSION_MAP.keys())}")
        raise typer.Exit(1)

    comp_ext = COMPRESSION_MAP[compression]

    # Set output directory
    if output_dir is None:
        output_dir = path
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Scanning {path}...[/bold]")

    # Collect files
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Collecting files...", total=None)
        files_to_archive, skipped_files, total_files = collect_files(
            path, max_file_size, min_file_size, exclude
        )
        progress.update(task, completed=True)

    if not files_to_archive:
        console.print("[yellow]No files found to archive.[/yellow]")
        return

    # Calculate statistics
    total_size = sum(size for _, size in files_to_archive)

    console.print(f"\n[bold]Collection Summary:[/bold]")
    console.print(f"  Total files scanned: {total_files:,}")
    console.print(f"  Files to archive: {len(files_to_archive):,}")
    console.print(f"  Total size to archive: {format_size(total_size)}")
    console.print(f"  Files skipped (too large): {len(skipped_files):,}")

    # Create batches
    batches = create_archive_batches(files_to_archive, max_archive_size, path)
    console.print(f"  Archives to create: {len(batches)}")

    if dry_run:
        console.print("\n[yellow]DRY RUN - No files will be modified[/yellow]")
        for i, batch in enumerate(batches, 1):
            batch_size = sum(size for _, size, _ in batch)
            console.print(f"  archive_{datetime.now().strftime('%Y%m%d')}_{i:03d}.tar.{comp_ext if comp_ext else 'tar'}")
            console.print(f"    Files: {len(batch):,}, Size: {format_size(batch_size)}")
        return

    # Create archives
    console.print("\n[bold]Creating archives...[/bold]")
    timestamp = datetime.now().strftime('%Y%m%d')
    successful_files = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Archiving...", total=len(batches))

        for i, batch in enumerate(batches, 1):
            # Generate archive name
            archive_name = f"archive_{timestamp}_{i:03d}.tar"
            if comp_ext:
                archive_name += f".{comp_ext}"

            archive_path = output_dir / archive_name

            # Create tarball
            if create_tarball(batch, archive_path, comp_ext):
                batch_size = sum(size for _, size, _ in batch)
                console.print(f"  ✓ {archive_name} ({len(batch):,} files, {format_size(batch_size)})")
                successful_files.extend([abs_path for abs_path, _, _ in batch])
            else:
                console.print(f"  ✗ {archive_name} (failed)")

            progress.update(task, advance=1)

    # Delete originals if requested
    if delete_originals and successful_files:
        console.print(f"\n[bold yellow]Deleting {len(successful_files):,} original files...[/bold yellow]")
        deleted = 0
        failed = 0

        for file_path in successful_files:
            try:
                file_path.unlink()
                deleted += 1
            except OSError:
                failed += 1

        console.print(f"  Deleted: {deleted:,}")
        if failed:
            console.print(f"  Failed: {failed:,}")

    console.print("\n[bold green]✓ Archiving complete[/bold green]")


if __name__ == "__main__":
    app()
