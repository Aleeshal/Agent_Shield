"""Save and load test runs in SQLite so runs can be compared.

One row per run. Results, summary and suggestions are stored as JSON text:
the data is small (tens of tests) and always read as a whole.
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from backend.config import settings

_lock = threading.Lock()
_JSON_COLS = ("results", "summary", "suggestions")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    label         TEXT NOT NULL,
    status        TEXT NOT NULL,          -- running | done | error
    parent_run_id TEXT,                   -- the run this one retests, if any
    instructions  TEXT NOT NULL,          -- snapshot used for the whole run
    model         TEXT NOT NULL,
    mock          INTEGER NOT NULL,
    total         INTEGER NOT NULL,
    completed     INTEGER NOT NULL DEFAULT 0,
    results       TEXT NOT NULL DEFAULT '[]',
    summary       TEXT,
    suggestions   TEXT,
    error         TEXT
);
CREATE TABLE IF NOT EXISTS app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@contextmanager
def _conn():
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.db_path, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        with _lock, con:
            yield con
    finally:
        con.close()


def init() -> None:
    with _conn() as con:
        con.executescript(SCHEMA)
        # A server restart kills background threads; don't leave runs stuck as "running".
        con.execute("UPDATE runs SET status='error', error='Server restarted during run.' "
                    "WHERE status='running'")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for col in _JSON_COLS:
        if col in d and d[col] is not None:
            d[col] = json.loads(d[col])
    d["mock"] = bool(d["mock"])
    return d


def create_run(run_id: str, label: str, instructions: str, total: int,
               parent_run_id: str | None = None) -> dict:
    with _conn() as con:
        con.execute(
            "INSERT INTO runs (id, created_at, label, status, parent_run_id, instructions, model, mock, total)"
            " VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?)",
            (run_id, _now(), label, parent_run_id, instructions, settings.model, int(settings.mock), total),
        )
    return get_run(run_id)


def update_progress(run_id: str, results: list[dict]) -> None:
    with _conn() as con:
        con.execute("UPDATE runs SET completed=?, results=? WHERE id=?",
                    (len(results), json.dumps(results), run_id))


def finish_run(run_id: str, results: list[dict], summary: dict) -> None:
    with _conn() as con:
        con.execute("UPDATE runs SET status='done', completed=?, results=?, summary=? WHERE id=?",
                    (len(results), json.dumps(results), json.dumps(summary), run_id))


def fail_run(run_id: str, error: str) -> None:
    with _conn() as con:
        con.execute("UPDATE runs SET status='error', error=? WHERE id=?", (error[:1000], run_id))


def save_suggestions(run_id: str, suggestions: dict) -> None:
    with _conn() as con:
        con.execute("UPDATE runs SET suggestions=? WHERE id=?", (json.dumps(suggestions), run_id))


def get_run(run_id: str) -> dict | None:
    with _conn() as con:
        return _row(con.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone())


def list_runs(limit: int = 50) -> list[dict]:
    """Newest first, without the heavy results/instructions columns."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, created_at, label, status, parent_run_id, model, mock, total, completed, summary"
            " FROM runs ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row(r) for r in rows]


def get_state(key: str) -> str | None:
    with _conn() as con:
        r = con.execute("SELECT value FROM app_state WHERE key=?", (key,)).fetchone()
    return r["value"] if r else None


def set_state(key: str, value: str | None) -> None:
    with _conn() as con:
        if value is None:
            con.execute("DELETE FROM app_state WHERE key=?", (key,))
        else:
            con.execute("INSERT INTO app_state (key, value) VALUES (?, ?)"
                        " ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
