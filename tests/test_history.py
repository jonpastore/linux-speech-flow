"""Tests for HistoryStore — SQLite-backed transcription history.

Uses a temporary file-based DB for each test (tmp_path fixture) so
tests are hermetic and don't touch the real ~/.local/share database.
"""
import os
import sqlite3
from pathlib import Path

import pytest

from linux_speech_flow.history import HistoryStore


def _make_entry(**kwargs):
    base = {
        "entry_type": "transcription",
        "created_at": "2024-01-01T12:00:00",
        "duration_sec": 1.5,
        "raw_text": "raw transcript",
        "processed_text": "processed transcript",
        "app_name": "gedit",
        "window_title": "untitled.txt",
    }
    base.update(kwargs)
    return base


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "test_history.db"
    return HistoryStore(db_path=db)


# ---------------------------------------------------------------------------
# Schema / initialization
# ---------------------------------------------------------------------------


class TestSchema:
    def test_creates_history_table(self, store, tmp_path):
        db = list(tmp_path.glob("*.db"))[0]
        conn = sqlite3.connect(db)
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        assert "history" in tables

    def test_second_init_does_not_raise(self, tmp_path):
        db = tmp_path / "test.db"
        HistoryStore(db_path=db)
        HistoryStore(db_path=db)  # should not raise


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


class TestInsert:
    def test_insert_returns_row_id(self, store):
        row_id = store.insert(_make_entry())
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_inserted_entry_retrievable(self, store):
        store.insert(_make_entry(raw_text="hello world"))
        rows = store.fetch_all()
        assert len(rows) == 1
        assert rows[0]["raw_text"] == "hello world"

    def test_multiple_entries_stored(self, store):
        store.insert(_make_entry(created_at="2024-01-01T10:00:00"))
        store.insert(_make_entry(created_at="2024-01-01T11:00:00"))
        store.insert(_make_entry(created_at="2024-01-01T12:00:00"))
        assert len(store.fetch_all()) == 3

    def test_entry_type_stored_correctly(self, store):
        store.insert(_make_entry(entry_type="conversation"))
        rows = store.fetch_all()
        assert rows[0]["entry_type"] == "conversation"

    def test_optional_fields_can_be_none(self, store):
        entry = {
            "entry_type": "transcription",
            "created_at": "2024-01-01T12:00:00",
        }
        row_id = store.insert(entry)
        assert row_id > 0
        rows = store.fetch_all()
        assert rows[0]["raw_text"] is None
        assert rows[0]["duration_sec"] is None


# ---------------------------------------------------------------------------
# max_entries pruning
# ---------------------------------------------------------------------------


class TestMaxEntries:
    def test_prunes_to_max_entries(self, store):
        for i in range(25):
            store.insert(
                _make_entry(
                    created_at=f"2024-01-{i+1:02d}T12:00:00",
                    raw_text=f"entry {i}",
                ),
                max_entries=20,
            )
        rows = store.fetch_all()
        assert len(rows) == 20

    def test_keeps_most_recent_entries(self, store):
        for i in range(10):
            store.insert(
                _make_entry(
                    created_at=f"2024-01-{i+1:02d}T12:00:00",
                    raw_text=f"entry {i}",
                ),
                max_entries=5,
            )
        rows = store.fetch_all()
        texts = [r["raw_text"] for r in rows]
        assert "entry 9" in texts  # most recent kept
        assert "entry 0" not in texts  # oldest pruned

    def test_max_entries_one_keeps_single_row(self, store):
        store.insert(
            _make_entry(created_at="2024-01-01T10:00:00", raw_text="first"),
            max_entries=1,
        )
        store.insert(
            _make_entry(created_at="2024-01-01T11:00:00", raw_text="second"),
            max_entries=1,
        )
        rows = store.fetch_all()
        assert len(rows) == 1
        assert rows[0]["raw_text"] == "second"


# ---------------------------------------------------------------------------
# fetch_all ordering
# ---------------------------------------------------------------------------


class TestFetchAll:
    def test_fetch_all_ordered_newest_first(self, store):
        store.insert(_make_entry(created_at="2024-01-01T10:00:00", raw_text="older"))
        store.insert(_make_entry(created_at="2024-01-01T12:00:00", raw_text="newer"))
        rows = store.fetch_all()
        assert rows[0]["raw_text"] == "newer"
        assert rows[1]["raw_text"] == "older"

    def test_fetch_all_empty_returns_empty_list(self, store):
        rows = store.fetch_all()
        assert rows == []


# ---------------------------------------------------------------------------
# clear_all
# ---------------------------------------------------------------------------


class TestClearAll:
    def test_clear_removes_all_entries(self, store):
        store.insert(_make_entry())
        store.insert(_make_entry())
        store.clear_all()
        assert store.fetch_all() == []

    def test_clear_on_empty_store_does_not_raise(self, store):
        store.clear_all()  # should not raise
        assert store.fetch_all() == []

    def test_insert_after_clear_works(self, store):
        store.insert(_make_entry(raw_text="before clear"))
        store.clear_all()
        store.insert(_make_entry(raw_text="after clear"))
        rows = store.fetch_all()
        assert len(rows) == 1
        assert rows[0]["raw_text"] == "after clear"

    def test_clear_vacuums_without_error(self, store):
        for _ in range(5):
            store.insert(_make_entry())
        store.clear_all()
        # VACUUM should have run; verify DB is still usable
        store.insert(_make_entry(raw_text="post-vacuum"))
        assert len(store.fetch_all()) == 1


# ---------------------------------------------------------------------------
# Row field access
# ---------------------------------------------------------------------------


class TestRowFields:
    def test_row_supports_column_name_access(self, store):
        store.insert(
            _make_entry(
                app_name="Terminal",
                window_title="bash",
                duration_sec=2.5,
            )
        )
        row = store.fetch_all()[0]
        assert row["app_name"] == "Terminal"
        assert row["window_title"] == "bash"
        assert row["duration_sec"] == pytest.approx(2.5)

    def test_row_id_is_autoincrement(self, store):
        id1 = store.insert(_make_entry(created_at="2024-01-01T10:00:00"))
        id2 = store.insert(_make_entry(created_at="2024-01-01T11:00:00"))
        assert id2 > id1


# ---------------------------------------------------------------------------
# File permissions
# ---------------------------------------------------------------------------


class TestPermissions:
    def test_db_permissions_0600(self, tmp_path):
        db = tmp_path / "perm_test.db"
        HistoryStore(db_path=db)
        mode = oct(os.stat(db).st_mode)[-4:]
        assert mode == "0600", f"Expected 0600, got {mode}"
