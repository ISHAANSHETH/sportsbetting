import sqlite3
import json
import time
import hashlib
import os
import tempfile
import functools
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "cache" / "sportsbetting.db"
FALLBACK_DB_PATH = Path(tempfile.gettempdir()) / "sportsbetting_cache.db"
_use_fallback = False


def _open(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            expires_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def _conn():
    return _open(FALLBACK_DB_PATH if _use_fallback else DB_PATH)


def _resilient(fn):
    """Retry once against a /tmp fallback DB if the primary path is read-only (e.g. serverless)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        global _use_fallback
        try:
            return fn(*args, **kwargs)
        except (OSError, sqlite3.OperationalError):
            if _use_fallback:
                raise
            _use_fallback = True
            return fn(*args, **kwargs)
    return wrapper


def _key(namespace: str, params: dict) -> str:
    raw = namespace + json.dumps(params, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


@_resilient
def get(namespace: str, params: dict):
    k = _key(namespace, params)
    with _conn() as conn:
        row = conn.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?", (k,)
        ).fetchone()
    if row and row[1] > time.time():
        return json.loads(row[0])
    return None


@_resilient
def set(namespace: str, params: dict, value, ttl_seconds: int = 86400):
    k = _key(namespace, params)
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
            (k, json.dumps(value), time.time() + ttl_seconds),
        )


@_resilient
def invalidate(namespace: str, params: dict):
    k = _key(namespace, params)
    with _conn() as conn:
        conn.execute("DELETE FROM cache WHERE key = ?", (k,))


@_resilient
def purge_expired():
    with _conn() as conn:
        conn.execute("DELETE FROM cache WHERE expires_at <= ?", (time.time(),))
