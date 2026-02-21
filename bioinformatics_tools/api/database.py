"""
SQLite database setup for BSP user accounts.

The database file location is controlled by the BSP_DB_PATH environment variable
(default: ~/.local/share/bsp/bsp.db). In Kubernetes, point this at a PersistentVolume
mount so user data survives pod restarts.

Usage:
    from bioinformatics_tools.api.database import init_db, get_db

    init_db()           # called once at app startup
    with get_db() as db:
        db.execute(...)
"""
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

LOGGER = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path.home() / '.local' / 'share' / 'bsp' / 'bsp.db'


def _get_db_path() -> Path:
    raw = os.getenv('BSP_DB_PATH')
    if raw:
        return Path(raw)
    return _DEFAULT_DB_PATH


def init_db() -> None:
    """Create the users table if it does not already exist. Safe to call on every startup."""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info('Initialising BSP database at %s', db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                username               TEXT    NOT NULL UNIQUE,
                password_hash          TEXT    NOT NULL,
                cluster_host           TEXT    NOT NULL,
                cluster_username       TEXT    NOT NULL,
                home_dir               TEXT    NOT NULL,
                private_key_encrypted  TEXT    NOT NULL,
                created_at             TEXT    NOT NULL
            )
        """)
        conn.commit()
        LOGGER.info('BSP database ready')
    finally:
        conn.close()


@contextmanager
def get_db():
    """Context manager yielding a sqlite3.Connection. Commits on clean exit, rolls back on error."""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
