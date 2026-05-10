"""SQLite helpers — connection, schema init, audit log writer."""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import config


def connect() -> sqlite3.Connection:
    """Open a SQLite connection.

    Default journal mode is MEMORY + synchronous=OFF — this is the only mode
    that works reliably on virtiofs/FUSE mounts (Cowork's sandbox mounts the
    project folder this way, and SQLite's WAL mode requires fsync semantics
    that FUSE doesn't fully provide). The trade-off is that a process crash
    could lose the last few rows; for a single-user tool that runs every few
    hours, that's fine.

    Power users on a real local filesystem who want WAL can set
    SIGNAL_BRAIN_JOURNAL_MODE=WAL in their environment.
    """
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None)  # autocommit
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    import os
    mode = os.environ.get("SIGNAL_BRAIN_JOURNAL_MODE", "MEMORY").upper()
    if mode == "WAL":
        conn.execute("PRAGMA journal_mode = WAL")
    else:
        conn.execute("PRAGMA journal_mode = MEMORY")
        conn.execute("PRAGMA synchronous = OFF")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    schema = Path(config.SCHEMA_PATH).read_text()
    with connect() as conn:
        conn.executescript(schema)


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    conn = connect()
    try:
        yield conn.cursor()
    finally:
        conn.close()


def log_audit(action: str, detail: str, metadata: dict[str, Any] | None = None) -> None:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO audit_log (action, detail, metadata) VALUES (?, ?, ?)",
            (action, detail, json.dumps(metadata) if metadata else None),
        )


def upsert_source(kind: str, handle: str, label: str) -> int:
    with cursor() as cur:
        cur.execute(
            """INSERT INTO sources (kind, handle, label) VALUES (?, ?, ?)
               ON CONFLICT(kind, handle) DO UPDATE SET label=excluded.label
               RETURNING id""",
            (kind, handle, label),
        )
        return cur.fetchone()[0]


def upsert_user_profile(name: str, role: str, company: str | None, bio: str,
                       interests: str, voice_notes: str | None = None) -> None:
    with cursor() as cur:
        cur.execute("""
            INSERT INTO user_profile (id, name, role, company, bio, interests, voice_notes, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, role=excluded.role, company=excluded.company,
                bio=excluded.bio, interests=excluded.interests, voice_notes=excluded.voice_notes,
                updated_at=datetime('now')
        """, (name, role, company, bio, interests, voice_notes))


def get_user_profile() -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM user_profile WHERE id = 1")
        row = cur.fetchone()
        return dict(row) if row else None
