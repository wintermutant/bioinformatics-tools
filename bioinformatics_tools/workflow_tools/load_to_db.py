"""
Load annotation tool output into a SQLite database.

Usage:
    python load_to_db.py gff  <input> <db_path> <source_tool> [--token <token_file>]
    python load_to_db.py csv  <input> <db_path> <table_name>  [--token <token_file>]
    python load_to_db.py tsv  <input> <db_path> <table_name>  [--token <token_file>]

Subcommands:
    gff  - Load GFF3 output (prodigal, etc.) into the `annotations` table
    csv  - Load any CSV with headers into a table named after the tool.
           Columns and types are inferred from the headers and data.
    tsv  - Load any TSV with headers into a table named after the tool.
           Same as csv but tab-delimited (e.g. COGclassifier output).

All subcommands write to the same .db file so all results live together.
"""
import argparse
import csv
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


# ─────────────────────────── Provenance ─────────────────────────── #

CREATE_RUN_LOG_SQL = """
CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_hash TEXT NOT NULL,
    tool TEXT NOT NULL,
    input_path TEXT,
    row_count INTEGER,
    loaded_at TEXT NOT NULL,
    UNIQUE(input_hash, tool)
);
"""


def _compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file's contents."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _already_loaded(db_path: str, input_hash: str, tool: str) -> bool:
    """Check if a file with this hash was already loaded for this tool."""
    if not Path(db_path).exists():
        return False
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(CREATE_RUN_LOG_SQL)
        row = conn.execute(
            "SELECT id FROM run_log WHERE input_hash = ? AND tool = ?",
            (input_hash, tool),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _record_load(db_path: str, input_hash: str, tool: str,
                 input_path: str, row_count: int) -> None:
    """Record a successful load in the run_log table."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(CREATE_RUN_LOG_SQL)
        conn.execute(
            "INSERT OR IGNORE INTO run_log (input_hash, tool, input_path, row_count, loaded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (input_hash, tool, input_path, row_count,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────── GFF loader ──────────────────────────── #

CREATE_GFF_TABLE_SQL = """
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
    gene_id TEXT,
    partial TEXT,
    start_type TEXT,
    rbs_motif TEXT,
    gc_content REAL,
    confidence REAL
);
"""

INSERT_GFF_SQL = """
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
    """Parse a GFF3 file and insert rows into the annotations table."""
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
                source_tool,
                type_,
                int(start),
                int(end),
                safe_float(score),
                strand,
                phase,
                attributes,
                attrs.get("ID"),
                attrs.get("partial"),
                attrs.get("start_type"),
                attrs.get("rbs_motif"),
                safe_float(attrs.get("gc_cont")),
                safe_float(attrs.get("conf")),
            ))

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(CREATE_GFF_TABLE_SQL)
        conn.executemany(INSERT_GFF_SQL, rows)
        conn.commit()
    finally:
        conn.close()

    return len(rows)


# ──────────────────────────── CSV loader ──────────────────────────── #

def _infer_type(value: str) -> str:
    """Guess SQLite column type from a sample value."""
    try:
        int(value)
        return "INTEGER"
    except ValueError:
        pass
    try:
        float(value)
        return "REAL"
    except ValueError:
        pass
    return "TEXT"


def load_csv_to_db(csv_path: str, db_path: str, table_name: str,
                   delimiter: str = ",") -> int:
    """Load a delimited file with headers into a table named `table_name`.

    - Creates the table from headers if it doesn't exist.
    - Infers column types (INTEGER/REAL/TEXT) from the first data row.
    - Adds an autoincrement `id` primary key.
    """
    with open(csv_path, newline="") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        headers = [h.strip() for h in next(reader)]
        data_rows = list(reader)

    if not data_rows:
        return 0

    # Infer types from the first row
    col_types = [_infer_type(val) for val in data_rows[0]]

    quoted_headers = [f'"{h}"' for h in headers]
    col_defs = ",\n    ".join(
        f'"{h}" {t}' for h, t in zip(headers, col_types)
    )
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        {col_defs}
    );
    """

    placeholders = ", ".join("?" for _ in headers)
    insert_sql = f"INSERT INTO {table_name} ({', '.join(quoted_headers)}) VALUES ({placeholders});"

    # Cast values to match inferred types
    def cast_row(row):
        result = []
        for val, typ in zip(row, col_types):
            val = val.strip()
            if not val:
                result.append(None)
            elif typ == "INTEGER":
                result.append(int(val))
            elif typ == "REAL":
                result.append(float(val))
            else:
                result.append(val)
        return tuple(result)

    rows = [cast_row(r) for r in data_rows]

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(create_sql)
        conn.executemany(insert_sql, rows)
        conn.commit()
    finally:
        conn.close()

    return len(rows)


# ──────────────────────────── CLI ──────────────────────────── #

def main():
    parser = argparse.ArgumentParser(description="Load annotation output into SQLite")
    sub = parser.add_subparsers(dest="format", required=True)

    # gff subcommand
    gff_p = sub.add_parser("gff", help="Load GFF3 file into the annotations table")
    gff_p.add_argument("input_file", help="Path to GFF3 file")
    gff_p.add_argument("db_path", help="Path to SQLite database")
    gff_p.add_argument("source_tool", help="Tool name (e.g. prodigal)")
    gff_p.add_argument("--token", help="Write a token file on success")

    # csv subcommand
    csv_p = sub.add_parser("csv", help="Load CSV file into a named table")
    csv_p.add_argument("input_file", help="Path to CSV file with headers")
    csv_p.add_argument("db_path", help="Path to SQLite database")
    csv_p.add_argument("table_name", help="Table name (e.g. pfam)")
    csv_p.add_argument("--token", help="Write a token file on success")

    # tsv subcommand
    tsv_p = sub.add_parser("tsv", help="Load TSV file into a named table")
    tsv_p.add_argument("input_file", help="Path to TSV file with headers")
    tsv_p.add_argument("db_path", help="Path to SQLite database")
    tsv_p.add_argument("table_name", help="Table name (e.g. cog)")
    tsv_p.add_argument("--token", help="Write a token file on success")

    args = parser.parse_args()

    if not Path(args.input_file).exists():
        print(f"ERROR: Input file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    if args.format == "gff":
        label = args.source_tool
    else:
        label = args.table_name

    # Check provenance: skip if this exact input was already loaded
    input_hash = _compute_file_hash(args.input_file)
    if _already_loaded(args.db_path, input_hash, label):
        print(f"Skipped {label}: input already loaded (hash {input_hash[:12]}...)")
        if args.token:
            Path(args.token).parent.mkdir(parents=True, exist_ok=True)
            Path(args.token).write_text(f"0 rows loaded from {label} (already in db)\n")
        return

    if args.format == "gff":
        n = load_gff_to_db(args.input_file, args.db_path, args.source_tool)
    elif args.format == "tsv":
        n = load_csv_to_db(args.input_file, args.db_path, args.table_name,
                           delimiter="\t")
    else:
        n = load_csv_to_db(args.input_file, args.db_path, args.table_name)

    _record_load(args.db_path, input_hash, label, args.input_file, n)
    print(f"Loaded {n} rows from {label} into {args.db_path}")

    if args.token:
        Path(args.token).parent.mkdir(parents=True, exist_ok=True)
        Path(args.token).write_text(f"{n} rows loaded from {label}\n")


if __name__ == "__main__":
    main()
