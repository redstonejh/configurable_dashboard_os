import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import get_app_settings


def get_db_path() -> str:
    settings = get_app_settings()
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    return settings.database_path


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                sensitive INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT NOT NULL UNIQUE,
                received_time TEXT NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL,
                owner TEXT,
                resource TEXT,
                summary TEXT,
                details TEXT,
                raw_payload TEXT,
                score INTEGER NOT NULL DEFAULT 0,
                score_label TEXT NOT NULL DEFAULT '',
                score_reasons TEXT NOT NULL DEFAULT '',
                rule_reason TEXT NOT NULL DEFAULT '',
                policy_version TEXT NOT NULL DEFAULT 'generic-rules-v1',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_records_received_time
                ON records(received_time);
            CREATE INDEX IF NOT EXISTS idx_records_grouping
                ON records(source, category, resource, received_time);

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                payload TEXT NOT NULL,
                error TEXT NOT NULL DEFAULT '',
                fingerprint TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(record_id) REFERENCES records(id)
            );

            CREATE TABLE IF NOT EXISTS rule_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(record_id) REFERENCES records(id)
            );

            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
