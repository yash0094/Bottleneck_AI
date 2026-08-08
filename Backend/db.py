"""
db.py — PostgreSQL access layer.

Deliberately raw SQL + psycopg2 (no ORM) to keep the project simple to read,
deploy, and debug. Works with any standard Postgres connection string —
Supabase, Render Postgres, Railway, local Postgres, etc.

Set DATABASE_URL, e.g.:
  postgresql://user:password@host:5432/dbname
  (Supabase: use the "Connection string" from Project Settings -> Database,
   URI / "Transaction" pooler mode is recommended for serverless-style hosts)
"""

import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from psycopg2.pool import SimpleConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to your environment "
        "(e.g. a Supabase or Render Postgres connection string)."
    )

# sslmode=require is needed by most managed Postgres providers (Supabase, Render).
_connect_kwargs = {}
if "sslmode" not in DATABASE_URL:
    _connect_kwargs["sslmode"] = "require"

_pool = SimpleConnectionPool(1, 10, dsn=DATABASE_URL, **_connect_kwargs)


@contextmanager
def get_cursor(commit: bool = False):
    """Context manager yielding a dict-cursor from the pool."""
    conn = _pool.getconn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        _pool.putconn(conn)


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    z_threshold REAL NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'upload',
    row_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS records (
    id SERIAL PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    result_json JSONB NOT NULL,
    z_threshold REAL NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_records_dataset ON records(dataset_id);
CREATE INDEX IF NOT EXISTS idx_datasets_user ON datasets(user_id);
CREATE INDEX IF NOT EXISTS idx_analyses_dataset ON analyses(dataset_id);
"""


def init_db():
    with get_cursor(commit=True) as cur:
        cur.execute(SCHEMA)
