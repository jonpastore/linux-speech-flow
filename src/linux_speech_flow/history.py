import os
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "linux-speech-flow" / "history.db"


class HistoryStore:
    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self.ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_type     TEXT NOT NULL DEFAULT 'transcription',
                    created_at     TEXT NOT NULL,
                    duration_sec   REAL,
                    raw_text       TEXT,
                    processed_text TEXT,
                    app_name       TEXT,
                    window_title   TEXT,
                    extra_json     TEXT
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_history_created_at
                ON history (created_at DESC)
            """
            )
        if self._db_path.exists():
            os.chmod(self._db_path, 0o600)

    def insert(self, entry: dict, max_entries: int = 20) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO history
                    (entry_type, created_at, duration_sec, raw_text,
                     processed_text, app_name, window_title, extra_json)
                VALUES
                    (:entry_type, :created_at, :duration_sec, :raw_text,
                     :processed_text, :app_name, :window_title, :extra_json)
                """,
                {
                    "entry_type": entry.get("entry_type", "transcription"),
                    "created_at": entry["created_at"],
                    "duration_sec": entry.get("duration_sec"),
                    "raw_text": entry.get("raw_text"),
                    "processed_text": entry.get("processed_text"),
                    "app_name": entry.get("app_name"),
                    "window_title": entry.get("window_title"),
                    "extra_json": entry.get("extra_json"),
                },
            )
            row_id = cursor.lastrowid
            conn.execute(
                """
                DELETE FROM history WHERE id NOT IN (
                    SELECT id FROM history ORDER BY created_at DESC LIMIT ?
                )
                """,
                (max_entries,),
            )
        return row_id

    def fetch_all(self) -> list:
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM history ORDER BY created_at DESC")
            return cursor.fetchall()

    def clear_all(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM history")
        conn = sqlite3.connect(self._db_path)
        conn.execute("VACUUM")
        conn.close()
