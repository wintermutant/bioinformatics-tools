'''
Extract archived files created by archive_files.py.
Optimized for speed with streaming extraction.
'''
import os
import tarfile
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

app = typer.Typer(help="Extract archived tarballs and restore directory structure")
console = Console()


def format_size(size_bytes: int) -> str:
    """Format bytes as human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def find_archives(path: Path, pattern: str) -> List[Path]:
    """Find all archive files matching pattern."""
    archives = []

    if path.is_file():
        # Single file provided
        if path.suffix in ['.tar', '.gz', '.bz2', '.xz', '.tgz', '.tbz2']:
            archives.append(path)
    else:
        # Directory - find all archives
        for root, _, files in os.walk(path):
            for filename in files:
                full_path = Path(root) / filename

                # Match pattern
                if pattern == '*':
                    if full_path.suffix in ['.tar', '.gz', '.bz2', '.xz', '.tgz', '.tbz2']:
                        archives.append(full_path)
                elif filename.endswith(pattern) or filename.endswith(pattern.lstrip('*')):
                    archives.append(full_path)

    return sorted(archives)


def list_archive_contents(archive_path: Path) -> List[tuple]:
    """List contents of an archive."""
    contents = []
    try:
        with tarfile.open(archive_path, 'r:*') as tar:
            for member in tar.getmembers():
                if member.isfile():
                    contents.append((member.name, member.size))
    except Exception as e:
        console.print(f"[red]Error reading {archive_path}: {e}[/red]")

    return contents


def extract_archive(archive_path: Path, output_dir: Path) -> tuple:
    """
    Extract a single archive.

    Returns:
        (success: bool, file_count: int, total_size: int)
    """
    try:
        file_count = 0
        total_size = 0

        with tarfile.open(archive_path, 'r:*') as tar:
            # Extract all members
            tar.extractall(path=output_dir)

            # Count files and size
            for member in tar.getmembers():
                if member.isfile():
                    file_count += 1
                    total_size += member.size

        return True, file_count, total_size

    except Exception as e:
        console.print(f"[red]Error extracting {archive_path}: {e}[/red]")
        return False, 0, 0


@app.command()
def main(
    path: Path = typer.Argument(
        ...,
        help="Archive file or directory containing archives",
        exists=True,
        resolve_path=True
    ),
    pattern: str = typer.Option(
        "*.tar.gz",
        "--pattern",
        "-p",
        help="Pattern to match archives (e.g., '*.tar.gz', 'archive_*.tar.xz')"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Directory to extract to (default: current directory)"
    ),
    delete_archives: bool = typer.Option(
        False,
        "--delete-archives",
        "-d",
        help="Delete archives after successful extraction"
    ),
    list_only: bool = typer.Option(
        False,
        "--list-only",
        "-l",
        help="List contents without extracting"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be extracted without doing it"
    ),
):
    """
    Extract archived tarballs and restore directory structure.

    Can extract a single archive or batch extract all archives in a directory.
    Preserves the original directory structure from the archives.

    Examples:
        # List contents of an archive
        misc extract_files archive_20251009_001.tar.gz --list-only

        # Extract single archive
        misc extract_files archive_20251009_001.tar.gz

        # Extract all archives in directory
        misc extract_files /path/to/archives

        # Extract and delete archives
        misc extract_files /path/to/archives --delete-archives

        # Extract with custom pattern
        misc extract_files /path/to/data -p "backup_*.tar.xz"
    """
    # Set output directory
    if output_dir is None:
        output_dir = Path.cwd()
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Find archives
    console.print(f"[bold]Searching for archives...[/bold]")
    archives = find_archives(path, pattern)

    if not archives:
        console.print(f"[yellow]No archives found matching pattern '{pattern}'[/yellow]")
        return

    console.print(f"  Found {len(archives)} archive(s)\n")

    # List only mode
    if list_only:
        for archive in archives:
            console.print(f"[bold cyan]{archive.name}[/bold cyan]")
            contents = list_archive_contents(archive)

            if contents:
                table = Table(show_header=True, header_style="bold")
                table.add_column("File", style="white")
                table.add_column("Size", justify="right", style="green")

                total_size = 0
                for file_path, size in contents:
                    table.add_row(file_path, format_size(size))
                    total_size += size

                console.print(table)
                console.print(f"  Total: {len(contents)} files, {format_size(total_size)}\n")
        return

    # Dry run mode
    if dry_run:
        console.print("[yellow]DRY RUN - No files will be extracted[/yellow]\n")
        total_files = 0
        total_size = 0

        for archive in archives:
            contents = list_archive_contents(archive)
            archive_size = sum(size for _, size in contents)
            total_files += len(contents)
            total_size += archive_size

            console.print(f"  {archive.name}")
            console.print(f"    Would extract {len(contents)} files ({format_size(archive_size)})")

        console.print(f"\n[bold]Total:[/bold]")
        console.print(f"  Archives: {len(archives)}")
        console.print(f"  Files: {total_files:,}")
        console.print(f"  Size: {format_size(total_size)}")
        return

    # Extract archives
    console.print(f"[bold]Extracting to {output_dir}...[/bold]\n")

    successful = []
    failed = []
    total_files = 0
    total_size = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Extracting...", total=len(archives))

        for archive in archives:
            success, file_count, size = extract_archive(archive, output_dir)

            if success:
                console.print(f"  ✓ {archive.name} ({file_count:,} files, {format_size(size)})")
                successful.append(archive)
                total_files += file_count
                total_size += size
            else:
                console.print(f"  ✗ {archive.name} (failed)")
                failed.append(archive)

            progress.update(task, advance=1)

    # Summary
    console.print(f"\n[bold]Extraction Summary:[/bold]")
    console.print(f"  Successful: {len(successful)}/{len(archives)}")
    console.print(f"  Files extracted: {total_files:,}")
    console.print(f"  Total size: {format_size(total_size)}")

    if failed:
        console.print(f"  [red]Failed: {len(failed)}[/red]")

    # Delete archives if requested
    if delete_archives and successful:
        console.print(f"\n[bold yellow]Deleting {len(successful)} archive(s)...[/bold yellow]")
        deleted = 0
        delete_failed = 0

        for archive in successful:
            try:
                archive.unlink()
                deleted += 1
            except OSError:
                delete_failed += 1

        console.print(f"  Deleted: {deleted}")
        if delete_failed:
            console.print(f"  Failed: {delete_failed}")

    console.print("\n[bold green]✓ Extraction complete[/bold green]")


if __name__ == "__main__":
    app()
