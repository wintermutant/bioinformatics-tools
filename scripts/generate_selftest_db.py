#!/usr/bin/env python3
"""
Generate test-files/sample.db with pre-cached placeholder BLOBs.

The DB mirrors the cache_map used by do_quick_example so that
restore_all() writes files to disk and snakemake sees outputs already exist.

Usage:
    python scripts/generate_selftest_db.py
"""
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "test-files" / "sample-a.txt"
OUTPUT_DB = PROJECT_ROOT / "test-files" / "sample.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS output_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_hash TEXT NOT NULL,
    tool TEXT NOT NULL,
    filename TEXT NOT NULL,
    content BLOB NOT NULL,
    size_bytes INTEGER NOT NULL,
    cached_at TEXT NOT NULL,
    UNIQUE(input_hash, tool, filename)
);
"""

# Same cache_map keys as do_quick_example (stem = "sample-a")
CACHE_ENTRIES = {
    "step_a": ["sample-a-step_a.out", "sample-a-step_a.extra"],
    "step_a_db": ["sample-a-step_a_db.tkn"],
    "step_b": ["sample-a-step_b.out"],
    "step_b_db": ["sample-a-step_b_db.tkn"],
    "step_c": ["sample-a-step_c.tsv", "sample-a-step_c_count.tsv"],
    "step_c_db": ["sample-a-step_c_db.tkn"],
}


def compute_hash(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    input_hash = compute_hash(INPUT_FILE)
    now = datetime.now(timezone.utc).isoformat()

    # Remove existing DB so we start fresh
    OUTPUT_DB.unlink(missing_ok=True)

    conn = sqlite3.connect(str(OUTPUT_DB))
    conn.execute(CREATE_TABLE_SQL)

    for tool, filenames in CACHE_ENTRIES.items():
        for fname in filenames:
            # Placeholder content — just enough for restore to write a non-empty file
            blob = f"# placeholder for {tool}/{fname}\n".encode()
            conn.execute(
                "INSERT INTO output_cache "
                "(input_hash, tool, filename, content, size_bytes, cached_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (input_hash, tool, fname, blob, len(blob), now),
            )

    conn.commit()
    conn.close()

    print(f"Created {OUTPUT_DB}")
    print(f"  input_hash: {input_hash}")
    print(f"  entries: {sum(len(v) for v in CACHE_ENTRIES.values())}")


if __name__ == "__main__":
    main()
