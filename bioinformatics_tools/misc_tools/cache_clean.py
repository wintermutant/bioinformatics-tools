'''
Recursively scan directories and remove common cache files/directories.
Useful for HPC users hitting file count limits.
'''
import os
import shutil
from pathlib import Path
import typer
from typing import List
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Clean cache directories to reduce file counts")
console = Console()

# Common cache patterns to remove
DEFAULT_CACHE_PATTERNS = [
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.ruff_cache',
    '.cache',
    'node_modules',
    '.npm',
    '.yarn',
    'venv/__pycache__',
    'env/__pycache__',
    '.tox',
    'htmlcov',
    '.coverage',
    '.eggs',
    '*.egg-info',
    'build/bdist.*',
    'build/lib',
    'dist',
    '.ipynb_checkpoints',
    '.Rhistory',
    '.RData',
    '.DS_Store',
]


def find_cache_dirs(root_path: Path, patterns: List[str], dry_run: bool = True) -> dict:
    """
    Find all cache directories matching patterns.
    """
    stats = {
        'dirs_found': 0,
        'files_found': 0,
        'total_size': 0,
        'dirs_removed': 0,
        'files_removed': 0,
        'space_freed': 0,
        'errors': []
    }

    items_to_remove = []

    # Walk the directory tree
    for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
        current_path = Path(dirpath)

        # Check directory names against patterns
        dirs_to_skip = []
        for dirname in dirnames:
            full_path = current_path / dirname

            # Check if directory matches any pattern
            if any(dirname == pattern or dirname.startswith(pattern.rstrip('*'))
                   for pattern in patterns if not pattern.startswith('*.')):
                try:
                    # Calculate size and file count
                    dir_size = sum(f.stat().st_size for f in full_path.rglob('*') if f.is_file())
                    file_count = sum(1 for _ in full_path.rglob('*') if _.is_file())

                    stats['dirs_found'] += 1
                    stats['files_found'] += file_count
                    stats['total_size'] += dir_size

                    items_to_remove.append({
                        'path': full_path,
                        'type': 'directory',
                        'size': dir_size,
                        'files': file_count
                    })

                    # Don't recurse into directories we're going to delete
                    dirs_to_skip.append(dirname)

                except (PermissionError, OSError) as e:
                    stats['errors'].append(f"Error accessing {full_path}: {e}")

        # Remove directories we're going to delete from the walk
        for skip in dirs_to_skip:
            dirnames.remove(skip)

        # Check filenames against patterns (for file-based caches)
        for filename in filenames:
            full_path = current_path / filename

            # Check if file matches any pattern
            if any(filename == pattern or
                   (pattern.startswith('*.') and filename.endswith(pattern[1:]))
                   for pattern in patterns):
                try:
                    file_size = full_path.stat().st_size

                    stats['files_found'] += 1
                    stats['total_size'] += file_size

                    items_to_remove.append({
                        'path': full_path,
                        'type': 'file',
                        'size': file_size,
                        'files': 1
                    })

                except (PermissionError, OSError) as e:
                    stats['errors'].append(f"Error accessing {full_path}: {e}")

    # Remove items if not dry run
    if not dry_run:
        for item in items_to_remove:
            try:
                if item['type'] == 'directory':
                    shutil.rmtree(item['path'])
                    stats['dirs_removed'] += 1
                else:
                    item['path'].unlink()

                stats['files_removed'] += item['files']
                stats['space_freed'] += item['size']

            except (PermissionError, OSError) as e:
                stats['errors'].append(f"Error removing {item['path']}: {e}")

    pretty_print = []
    for item in items_to_remove:
        pretty_print.append(f"{item['type'].capitalize()}: {item['path']}, {format_size(item['size'])})")
    prettier_print = "\n".join(pretty_print)
    print(prettier_print)

    return stats, items_to_remove


def format_size(size_bytes: int) -> str:
    """Format bytes as human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


@app.command()
def main(
    path: Path = typer.Argument(
        ...,
        help="Directory to scan for cache files",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--execute",
        help="Show what would be deleted without actually deleting"
    ),
    patterns: List[str] = typer.Option(
        None,
        "--pattern",
        "-p",
        help="Additional cache patterns to match (can be used multiple times)"
    ),
    show_items: bool = typer.Option(
        False,
        "--show-items",
        "-s",
        help="Show individual items that would be removed"
    ),
):
    """
    Scan directory recursively and remove cache files/directories.

    By default runs in dry-run mode (shows what would be deleted).
    Use --execute to actually delete the cache files.

    Examples:
        # Dry run (safe, shows what would be deleted)
        misc cache-clean /path/to/directory

        # Actually delete cache files
        misc cache-clean /path/to/directory --execute

        # Add custom patterns
        misc cache-clean /path/to/directory -p ".snakemake" -p "work"

        # Show all items found
        misc cache-clean /path/to/directory --show-items
    """
    # Combine default patterns with user-provided ones
    all_patterns = DEFAULT_CACHE_PATTERNS.copy()
    if patterns:
        all_patterns.extend(patterns)

    # Show mode
    mode_text = "[yellow]DRY RUN MODE[/yellow]" if dry_run else "[red]EXECUTE MODE[/red]"
    console.print(f"\n{mode_text} - Scanning {path}\n")

    # Run the scan
    with console.status("[bold green]Scanning directories..."):
        stats, items = find_cache_dirs(path, all_patterns, dry_run)

    # Show items if requested
    if show_items and items:
        table = Table(title="Cache Items Found")
        table.add_column("Type", style="cyan")
        table.add_column("Path", style="white")
        table.add_column("Files", justify="right", style="yellow")
        table.add_column("Size", justify="right", style="green")

        for item in items:
            table.add_row(
                item['type'],
                str(item['path']),
                str(item['files']),
                format_size(item['size'])
            )

        console.print(table)
        console.print()

    # Show summary
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Directories found: {stats['dirs_found']}")
    console.print(f"  Individual files found: {stats['files_found']}")
    console.print(f"  Total files: {stats['files_found']}")
    console.print(f"  Total size: {format_size(stats['total_size'])}")

    if not dry_run:
        console.print(f"\n[bold green]Removed:[/bold green]")
        console.print(f"  Directories: {stats['dirs_removed']}")
        console.print(f"  Files: {stats['files_removed']}")
        console.print(f"  Space freed: {format_size(stats['space_freed'])}")

    if stats['errors']:
        console.print(f"\n[bold red]Errors ({len(stats['errors'])}):[/bold red]")
        for error in stats['errors'][:10]:  # Show first 10 errors
            console.print(f"  {error}")
        if len(stats['errors']) > 10:
            console.print(f"  ... and {len(stats['errors']) - 10} more errors")

    if dry_run and stats['total_size'] > 0:
        console.print("\n[yellow]This was a dry run. Use --execute to actually delete these files.[/yellow]")


if __name__ == "__main__":
    app()
