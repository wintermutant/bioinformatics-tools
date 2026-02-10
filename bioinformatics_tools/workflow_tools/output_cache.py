"""
DB-based output cache for MARGIE workflow.

Stores compute rule output files (prodigal, pfam, cog) as BLOBs in an
``output_cache`` table inside the same SQLite database used for annotations.
This lets Snakemake skip expensive re-computation when the same input FASTA
has already been processed, even across fresh timestamped working directories.

Copy the ``.db`` file to another server and it carries the cached outputs
with it — no separate cache directory needed.
"""
import hashlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger(__name__)

CREATE_OUTPUT_CACHE_SQL = """
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


def _compute_file_hash(file_path: str) -> str:
    """Return first 16 hex chars of the SHA-256 of *file_path*."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_OUTPUT_CACHE_SQL)


# ───────────────────────── single-tool helpers ───────────────────────── #

def restore(db_path: str, input_file: str, tool_name: str,
            output_paths: list[str]) -> bool:
    """Restore cached outputs for *tool_name* from the DB.

    Returns True if **all** expected files were found in the cache and
    written to disk, False on any miss.
    """
    if not Path(db_path).exists():
        return False

    input_hash = _compute_file_hash(input_file)
    expected = {Path(p).name for p in output_paths}

    conn = sqlite3.connect(db_path)
    try:
        _ensure_table(conn)
        rows = conn.execute(
            "SELECT filename, content FROM output_cache "
            "WHERE input_hash = ? AND tool = ?",
            (input_hash, tool_name),
        ).fetchall()
    finally:
        conn.close()

    cached = {fname: blob for fname, blob in rows}

    if not expected.issubset(cached.keys()):
        return False

    # Write BLOBs to the expected output paths
    for path in output_paths:
        fname = Path(path).name
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(cached[fname])
        LOGGER.info("Restored from cache: %s", path)

    return True


def store(db_path: str, input_file: str, tool_name: str,
          output_paths: list[str]) -> None:
    """Read each output file and INSERT OR REPLACE into output_cache.

    Missing files are skipped (handles partial workflow success).
    """
    input_hash = _compute_file_hash(input_file)
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(db_path)
    try:
        _ensure_table(conn)
        for path in output_paths:
            p = Path(path)
            if not p.exists():
                LOGGER.debug("Skipping cache store for missing file: %s", path)
                continue
            blob = p.read_bytes()
            conn.execute(
                "INSERT OR REPLACE INTO output_cache "
                "(input_hash, tool, filename, content, size_bytes, cached_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (input_hash, tool_name, p.name, blob, len(blob), now),
            )
        conn.commit()
    finally:
        conn.close()


# ──────────────────────── multi-tool wrappers ──────────────────────── #

def restore_all(db_path: str, input_file: str,
                tool_outputs_map: dict[str, list[str]]) -> dict[str, bool]:
    """Restore cached outputs for every tool in *tool_outputs_map*.

    Returns ``{tool_name: hit_bool}`` so the caller can log which tools
    were restored.
    """
    results: dict[str, bool] = {}
    for tool_name, output_paths in tool_outputs_map.items():
        hit = restore(db_path, input_file, tool_name, output_paths)
        results[tool_name] = hit
        if hit:
            LOGGER.info("Cache HIT for %s — skipping recomputation", tool_name)
        else:
            LOGGER.info("Cache miss for %s — will compute", tool_name)
    return results


def store_all(db_path: str, input_file: str,
              tool_outputs_map: dict[str, list[str]]) -> None:
    """Store outputs for every tool in *tool_outputs_map* into the DB."""
    for tool_name, output_paths in tool_outputs_map.items():
        store(db_path, input_file, tool_name, output_paths)
        LOGGER.info("Cached outputs for %s", tool_name)
