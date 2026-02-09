"""
Load annotation tool output into a SQLite database.

Usage:
    python load_to_db.py <input_gff> <db_path> <source_tool> [--token <token_file>]

Designed to be called from Snakemake rules after each annotation tool runs.
Parses GFF3 output (prodigal, etc.) and inserts rows into an existing SQLite DB.

The `annotations` table is created if it doesn't already exist, so you can
point multiple tools at the same DB and they'll all land in one table
differentiated by the `source` column.
"""
import argparse
import sqlite3
import sys
from pathlib import Path


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seqid TEXT NOT NULL,
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    start INTEGER NOT NULL,
    end INTEGER NOT NULL,
    score REAL,
    strand TEXT,
    phase TEXT,
    attributes TEXT,
    -- parsed from prodigal GFF attributes --
    gene_id TEXT,
    partial TEXT,
    start_type TEXT,
    rbs_motif TEXT,
    gc_content REAL,
    confidence REAL
);
"""

INSERT_SQL = """
INSERT INTO annotations
    (seqid, source, type, start, end, score, strand, phase, attributes,
     gene_id, partial, start_type, rbs_motif, gc_content, confidence)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


def parse_attributes(attr_string: str) -> dict:
    """Parse GFF3 attribute column (key=value;key=value) into a dict."""
    attrs = {}
    for pair in attr_string.strip().rstrip(";").split(";"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            attrs[key.strip()] = value.strip()
    return attrs


def safe_float(value: str | None) -> float | None:
    if value is None or value == ".":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_gff_to_db(gff_path: str, db_path: str, source_tool: str) -> int:
    """Parse a GFF3 file and insert rows into the annotations table.

    Returns the number of rows inserted.
    """
    rows = []
    with open(gff_path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) != 9:
                continue

            seqid, source, type_, start, end, score, strand, phase, attributes = cols
            attrs = parse_attributes(attributes)

            rows.append((
                seqid,
                source_tool,       # use the explicit tool name, not the GFF source col
                type_,
                int(start),
                int(end),
                safe_float(score),
                strand,
                phase,
                attributes,        # keep raw attributes for reference
                attrs.get("ID"),
                attrs.get("partial"),
                attrs.get("start_type"),
                attrs.get("rbs_motif"),
                safe_float(attrs.get("gc_cont")),
                safe_float(attrs.get("conf")),
            ))

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.executemany(INSERT_SQL, rows)
        conn.commit()
    finally:
        conn.close()

    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Load GFF annotation output into SQLite")
    parser.add_argument("input_gff", help="Path to GFF3 file from annotation tool")
    parser.add_argument("db_path", help="Path to existing SQLite database")
    parser.add_argument("source_tool", help="Name of the annotation tool (e.g. prodigal)")
    parser.add_argument("--token", help="Path to write a token file on success")
    args = parser.parse_args()

    if not Path(args.input_gff).exists():
        print(f"ERROR: Input file not found: {args.input_gff}", file=sys.stderr)
        sys.exit(1)

    n = load_gff_to_db(args.input_gff, args.db_path, args.source_tool)
    print(f"Loaded {n} annotations from {args.source_tool} into {args.db_path}")

    if args.token:
        Path(args.token).parent.mkdir(parents=True, exist_ok=True)
        Path(args.token).write_text(f"{n} rows loaded from {args.source_tool}\n")


if __name__ == "__main__":
    main()
