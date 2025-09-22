import typer
from pathlib import Path
from typing import Optional

app = typer.Typer()

@app.command()
def main(
    # file: Path = typer.Argument(..., help="Input file to process", metavar="file"),
    file: Path = typer.Argument(..., help="Input file to process"),
    output: Optional[Path] = typer.Option("default.out", "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    count: int = typer.Option(10, "--count", "-c", help="Number of items to process")
):
    """
    Test script demonstrating typer integration with misc dispatcher.

    This script shows how to use type hints and typer for automatic CLI generation.
    """
    print(f"Processing file: {file}")
    print(f"Output will be written to: {output}")
    print(f"Verbose mode: {'enabled' if verbose else 'disabled'}")
    print(f"Processing count: {count}")

    if not file.exists():
        print(f"⚠️  Warning: Input file '{file}' does not exist")

    print("✅ Test completed successfully!")
