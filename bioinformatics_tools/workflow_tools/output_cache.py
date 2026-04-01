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
import time
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


def _get_connection(db_path: str, timeout: float = 30.0) -> sqlite3.Connection:
    """Create a SQLite connection configured for network filesystems.

    Args:
        db_path: Path to the SQLite database file
        timeout: Connection timeout in seconds (default 30s for NFS)

    Returns:
        Configured sqlite3.Connection with increased timeout and busy handler
    """
    conn = sqlite3.connect(db_path, timeout=timeout)

    # Set busy timeout (milliseconds) - wait up to 30s for locks
    # This is critical for NFS where lock operations are slow
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")

    return conn


def _retry_operation(func, max_retries: int = 3, initial_delay: float = 0.5):
    """Retry operations that fail with transient disk I/O or lock errors.

    Args:
        func: Callable to execute
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (doubles each time)

    Returns:
        Result of func() if successful

    Raises:
        sqlite3.OperationalError: If all retries fail
    """
    delay = initial_delay
    last_error = None

    for attempt in range(max_retries):
        try:
            return func()
        except sqlite3.OperationalError as e:
            last_error = e
            error_str = str(e).lower()

            # Retry on transient errors
            if any(err in error_str for err in ["disk i/o error", "database is locked", "unable to open"]):
                if attempt < max_retries - 1:
                    LOGGER.warning(
                        "Database operation failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt + 1, max_retries, e, delay
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    LOGGER.error("Database operation failed after %d attempts: %s", max_retries, e)
            else:
                # Not a transient error, re-raise immediately
                raise

    raise last_error


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

def _extract_pattern_suffix(filename: str) -> str:
    """Extract the pattern suffix for matching across different stems.

    Files follow two patterns:
    1. With stem: "{stem}-{rest}" → pattern = "-{rest}"
    2. Without stem: "{filename}" → pattern = "{filename}"

    Examples:
        'genome-a-prodigal.gff' → '-prodigal.gff'
        'genome-b-prodigal_db.tkn' → '-prodigal_db.tkn'
        'pfam.tsv' → 'pfam.tsv'
        'cog_classify.tsv' → 'cog_classify.tsv'
    """
    # If filename contains a dash, assume it's {stem}-{rest}
    # Pattern is everything from first dash onwards
    if '-' in filename:
        return '-' + filename.split('-', 1)[1]
    # Otherwise, it's a fixed filename without stem
    return filename


def restore(db_path: str, input_file: str, tool_name: str,
            output_paths: list[str]) -> bool:
    """Restore cached outputs for *tool_name* from the DB using pattern matching.

    Matches files by pattern suffix rather than exact filename, allowing cache hits
    across different input filenames with identical content.

    Examples:
        Cached: genome-a-prodigal.gff (pattern: -prodigal.gff)
        Expected: genome-b-prodigal.gff (pattern: -prodigal.gff) → MATCH!

        Cached: pfam.tsv (pattern: pfam.tsv)
        Expected: pfam.tsv (pattern: pfam.tsv) → MATCH!

    Returns True if **all** expected files were found in the cache and
    written to disk, False on any miss.
    """
    if not Path(db_path).exists():
        return False

    input_hash = _compute_file_hash(input_file)

    conn = _get_connection(db_path)
    try:
        _ensure_table(conn)
        rows = conn.execute(
            "SELECT filename, content FROM output_cache "
            "WHERE input_hash = ? AND tool = ?",
            (input_hash, tool_name),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        LOGGER.info("Cache miss for %s: no cached files found for this input", tool_name)
        return False

    # Build pattern -> blob mapping from cached files
    cached_patterns = {}
    for fname, blob in rows:
        pattern = _extract_pattern_suffix(fname)
        cached_patterns[pattern] = blob

    # Match expected files by pattern
    matched = {}
    for path in output_paths:
        expected_fname = Path(path).name
        expected_pattern = _extract_pattern_suffix(expected_fname)

        if expected_pattern in cached_patterns:
            matched[path] = cached_patterns[expected_pattern]
        else:
            LOGGER.info("Cache miss for %s: no match for pattern '%s' (file: %s)",
                       tool_name, expected_pattern, expected_fname)
            LOGGER.debug("Available patterns: %s", list(cached_patterns.keys()))
            return False

    # Write all matched BLOBs to expected paths
    for path, blob in matched.items():
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(blob)
        LOGGER.info("Restored from cache: %s", path)

    return True


def store(db_path: str, input_file: str, tool_name: str,
          output_paths: list[str]) -> None:
    """Read each output file and INSERT OR REPLACE into output_cache.

    Missing files are skipped (handles partial workflow success).
    """
    input_hash = _compute_file_hash(input_file)
    now = datetime.now(timezone.utc).isoformat()

    # Ensure parent directory exists before creating database
    db_path_obj = Path(db_path).expanduser()
    db_path_obj.parent.mkdir(parents=True, exist_ok=True)

    conn = _get_connection(str(db_path_obj))
    try:
        _ensure_table(conn)
        for path in output_paths:
            p = Path(path)
            if not p.exists():
                LOGGER.debug("Skipping cache store for missing file: %s", path)
                continue
            file_size = p.stat().st_size
            size_mb = file_size / (1024 * 1024)
            if size_mb > 1:
                LOGGER.info("  Reading %s (%.1f MB)...", p.name, size_mb)
            blob = p.read_bytes()
            conn.execute(
                "INSERT OR REPLACE INTO output_cache "
                "(input_hash, tool, filename, content, size_bytes, cached_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (input_hash, tool_name, p.name, blob, len(blob), now),
            )
            if size_mb > 1:
                LOGGER.info("  ✓ Stored %s", p.name)
        conn.commit()
    finally:
        conn.close()


# ──────────────────────── multi-tool wrappers ──────────────────────── #

def restore_all(db_path: str, input_file: str,
                build_filepaths_map: dict[str, list[str]]) -> dict[str, bool]:
    """Restore cached outputs for every tool in *build_filepaths_map*.

    Returns ``{tool_name: hit_bool}`` so the caller can log which tools
    were restored.
    """
    results: dict[str, bool] = {}
    for tool_name, output_paths in build_filepaths_map.items():
        hit = restore(db_path, input_file, tool_name, output_paths)
        results[tool_name] = hit
        if hit:
            LOGGER.info("Cache HIT for %s — skipping recomputation", tool_name)
        else:
            LOGGER.info("Cache miss for %s — will compute", tool_name)
    return results


def store_all(db_path: str, input_file: str,
              build_filepaths_map: dict[str, list[str]]) -> None:
    """Store outputs for every tool in *build_filepaths_map* into the DB."""
    total_tools = len(build_filepaths_map)
    LOGGER.info("Storing outputs to cache for %d tools...", total_tools)
    for idx, (tool_name, output_paths) in enumerate(build_filepaths_map.items(), 1):
        LOGGER.info("Caching %s (%d/%d)...", tool_name, idx, total_tools)
        store(db_path, input_file, tool_name, output_paths)
        LOGGER.info("✓ Cached outputs for %s", tool_name)


CREATE_RUN_LOG_SQL = """
CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    tool TEXT NOT NULL,
    input_path TEXT,
    row_count INTEGER,
    rules_completed INTEGER,
    status TEXT NOT NULL,
    loaded_at TEXT NOT NULL
);
"""


def log_workflow_run(db_path: str, run_id: str, input_file: str, workflow_name: str,
                     rules_completed: int = 0, status: str = 'success') -> None:
    """Insert a run_log row for this workflow execution.

    The caller supplies the run_id (generated at the start of the pipeline) so
    the same UUID covers the full run, including failure cases.

    row_count is always 0 here — it is only meaningful for annotation loaders
    (load_to_db.py). rules_completed holds the number of snakemake rules that
    finished in this run.

    This function is non-fatal: any errors are logged as warnings but do not
    crash the workflow. The workflow run itself has already succeeded/failed.
    """
    try:
        if not Path(db_path).exists():
            LOGGER.warning("Cannot write run_log: db not found at %s", db_path)
            return

        input_hash = _compute_file_hash(input_file)
        now = datetime.now(timezone.utc).isoformat()

        def _log_run():
            """Inner function for retry wrapper."""
            conn = _get_connection(db_path, timeout=30.0)
            try:
                conn.execute(CREATE_RUN_LOG_SQL)
                conn.execute(
                    "INSERT INTO run_log "
                    "(run_id, input_hash, tool, input_path, row_count, rules_completed, status, loaded_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (run_id, input_hash, workflow_name, input_file, 0, rules_completed, status, now),
                )
                conn.commit()
            finally:
                conn.close()

        # Retry on transient I/O errors (NFS, lock contention, etc.)
        _retry_operation(_log_run, max_retries=3, initial_delay=0.5)

        LOGGER.info("Logged workflow run: %s run_id=%s status=%s rules_completed=%d (hash %s...)",
                    workflow_name, run_id, status, rules_completed, input_hash[:12])

    except Exception as e:
        # Non-fatal: log the error but don't crash the workflow
        LOGGER.warning(
            "Failed to log workflow run to database (non-fatal): %s. "
            "Workflow execution was %s, but logging failed.",
            e, status
        )
