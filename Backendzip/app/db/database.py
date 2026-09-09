"""
SQLite is a deliberate choice, not a shortcut we're apologizing for.

A session represents one isolated analysis run.

Each session can contain multiple PDFs. Documents, claims, and
relationships created during that run remain isolated from other sessions.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager


DB_PATH = Path(__file__).resolve().parents[2] / "data" / "superjoin.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT DEFAULT 'active'
);


CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    filename TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    page_count INTEGER,
    status TEXT DEFAULT 'pending'
);


CREATE TABLE IF NOT EXISTS evidence_blocks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    page INTEGER NOT NULL,
    block_type TEXT NOT NULL,
    text TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    evidence_block_id TEXT REFERENCES evidence_blocks(id),

    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,

    value REAL,
    value_type TEXT,
    unit TEXT,

    period_start TEXT,
    period_end TEXT,
    period_type TEXT,

    scope TEXT,
    basis TEXT,
    definition TEXT,

    claim_type TEXT,

    source_page INTEGER NOT NULL,
    source_text TEXT NOT NULL,
    verified INTEGER DEFAULT 0,

    confidence REAL,
    created_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_claim_id TEXT NOT NULL REFERENCES claims(id),
    target_claim_id TEXT NOT NULL REFERENCES claims(id),

    relationship_type TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    explanation TEXT NOT NULL,
    confidence REAL,

    decided_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS predicate_registry (
    predicate TEXT PRIMARY KEY,
    first_seen_document_id TEXT,
    example_definition TEXT
);
"""


def init_db():
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    try:
        yield conn
        conn.commit()

    finally:
        conn.close()