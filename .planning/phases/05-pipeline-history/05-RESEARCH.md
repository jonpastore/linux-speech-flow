# Phase 5: Pipeline History - Research

**Researched:** 2026-02-21
**Domain:** SQLite persistence + GTK4 expandable list UI
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Log entry layout:**
- Compact rows as default: shows timestamp + duration + processed transcript preview (truncated)
- Newest-first ordering
- Click to expand inline — row grows below the compact row
- Expanded shows: full processed transcript, then raw transcript below it, plus app/window title and duration

**Transcript display:**
- Both processed and raw transcripts shown in the expanded row (raw below processed)
- Full text — scrollable within the row if long (no height cap)
- Color/background distinction between processed (primary) and raw (secondary/muted shade)
- Copy button per transcript section (one for processed, one for raw)

**Window behavior:**
- Live updates: new entries appear at the top as transcriptions complete, window stays usable
- Focus existing window if already open (single-instance)
- Persist window position + size between opens
- Window title: "linux-speech-flow — History"
- Tray menu item label: "Transcription History"

**Empty state:**
- Simple centered message: "No transcriptions yet. Press [hotkey] to start recording."
- Hotkey shown should reflect the current configured hotkey (read from settings)

**Interactions and storage management:**
- "Clear All History" button: available both in the history window header/toolbar AND in Settings
- Clearing logs requires a confirmation dialog: "Clear all transcription history? This cannot be undone." with Cancel / Clear buttons
- "Clear Temp Audio Files" button: in both history window footer AND Settings (Maintenance/Storage section)
- Max entries limit: configurable in Settings (default 20; user can raise/lower)
- Manual GC trigger: run cleanup on demand, available in both history window and Settings

**Extensibility note (Phase 6 Conversation Mode):**
- Phase 6 will add conversation sessions to this same history window as a distinct row type
- The SQLite schema and history window must be designed to accommodate a second entry type with different fields (file path, AI confidence, resume status)
- Phase 5 does NOT implement conversation mode — but must not make the schema/window un-extendable

### Claude's Discretion

- Exact color/shade for background distinction between processed and raw
- Compact row preview truncation length
- Copy button icon vs label
- Exact layout of history window footer controls
- Settings section name for storage management (e.g. "Maintenance", "Storage", "History")

### Deferred Ideas (OUT OF SCOPE)

- Rename FreeFlow → linux-speech-flow (resolved in Phase 4.1)
- Hotkey customization in Settings (own phase)
- Tray menu hotkey hints (Phase 4 enhancement)
- Phase 6: Conversation Mode (extends Phase 5's history window)
- Slack integration (future phase)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HIST-01 | Each transcription run is stored locally: timestamp, raw transcript, processed transcript, window context, duration | SQLite via Python stdlib sqlite3 — schema design section covers all fields; write from transcription worker thread via per-thread connection |
| HIST-02 | Up to 20 most recent runs are retained (SQLite in ~/.local/share/linux-speech-flow/) | Prune-on-insert pattern with DELETE subquery; `history_max_entries` config key added to DEFAULT_CONFIG |
| HIST-03 | User can view run log as a GTK window launched from tray menu | HistoryWindow (Gtk.ApplicationWindow) with Gtk.ListBox expandable rows; single-instance via present(); tray menu wired in app.py |
</phase_requirements>

## Summary

Phase 5 requires two distinct deliverables: (1) a SQLite persistence layer that writes every transcription run from the background pipeline thread, and (2) a GTK 4 window that displays those runs with expandable rows, live updates, and storage management controls.

The storage layer is straightforward: Python's stdlib `sqlite3` module (already available, no new dependency) writes to `~/.local/share/linux-speech-flow/history.db`. The key threading constraint is that the existing `TranscriptionPipeline._process()` runs on a daemon worker thread, so it must open its own SQLite connection per call (not share a connection with the GTK main thread). WAL journal mode enables concurrent reads from the history window without blocking writes.

The GTK 4 UI uses `Gtk.ListBox` with custom `Gtk.ListBoxRow` subclasses. Each row holds a compact summary widget and a hidden detail widget; clicking activates the row and toggles detail visibility. Live updates arrive via `GLib.idle_add()` from the pipeline thread, prepending new rows to the top. Single-instance behavior reuses the existing pattern from `app.py` (check for existing window, call `present()` if found). Window size persistence uses `get_default_size()` / `set_default_size()` saved to config.json on `close-request`.

**Primary recommendation:** Use stdlib `sqlite3` with WAL mode + per-thread connections. Use `Gtk.ListBox` + custom row subclasses with toggled child widget visibility for expand/collapse. Wire history write into `TranscriptionPipeline._process()` just before the `_on_paste_complete` callback.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib (Python 3.10+) / SQLite 3.37.2 | Local history storage | Zero dependency, bundled with Python, already available in venv |
| gi.repository.Gtk (GTK 4.6.9) | 4.6.9 (system) | History window and expandable list UI | Already used throughout codebase |
| gi.repository.GLib | same | Thread-safe GTK updates via idle_add | Already used in TranscriptionPipeline |
| gi.repository.Gdk | same | Clipboard copy for transcript text | Already available |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib.Path | stdlib | DB path construction (~/.local/share/...) | Already used in config.py and transcription.py |
| threading.Lock | stdlib | Serialize writes if multiple threads ever write simultaneously | Defensive; current architecture has single writer thread |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib sqlite3 | SQLAlchemy | No benefit for a simple 1-table schema; avoids new dependency |
| stdlib sqlite3 | peewee ORM | Same — overkill for Phase 5; avoid new dependency |
| Gtk.ListBox rows | Gtk.ColumnView / Gtk.ListView (model-based) | Model-based widgets are more complex; ListBox is simpler and matches codebase patterns for small datasets (max 20–100 entries) |
| config.json for window size | GSettings | GSettings requires a compiled schema; config.json already exists and is used for all other persistence |

**Installation:** No new pip packages required. sqlite3 is stdlib. GTK 4 already installed.

## Architecture Patterns

### Recommended Project Structure

```
src/linux_speech_flow/
├── history.py           # HistoryStore class — SQLite schema, CRUD, pruning
├── history_window.py    # HistoryWindow GTK class — list display, expand/collapse
├── transcription.py     # Modified: call HistoryStore.insert() in _process()
├── app.py               # Modified: add _history_window, on_open_history handler
├── tray.py              # Modified: add "Transcription History" menu item
├── config.py            # Modified: add history_max_entries to DEFAULT_CONFIG
└── settings.py          # Modified: add History/Maintenance section with Clear + max entries
```

### Pattern 1: SQLite Schema — Extensible Entry Types

**What:** Single `history` table with an `entry_type` discriminator column. Phase 5 writes `entry_type='transcription'`. Phase 6 will write `entry_type='conversation'`. Extra fields for conversation mode (file_path, ai_confidence, resume_status) can be NULL for transcription rows.

**When to use:** Whenever a history window must accommodate multiple distinct row types with different fields.

```python
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_type    TEXT NOT NULL DEFAULT 'transcription',
    created_at    TEXT NOT NULL,
    duration_sec  REAL,
    raw_text      TEXT,
    processed_text TEXT,
    app_name      TEXT,
    window_title  TEXT,
    extra_json    TEXT
)
"""

CREATE_IDX_SQL = """
CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC)
"""
```

**Key design points:**
- `extra_json` is a TEXT column holding a JSON blob for Phase 6's extra fields (file_path, ai_confidence, resume_status). NULL for Phase 5 rows.
- `created_at` is ISO8601 string (`datetime.utcnow().isoformat()`) for portable sorting.
- `entry_type` allows the HistoryWindow to render different row templates per type.

### Pattern 2: Per-Thread SQLite Connections (Writer Thread)

**What:** The TranscriptionPipeline worker thread creates its own connection per `_process()` call (or per worker lifetime). The GTK main thread creates a separate read-only connection for the HistoryWindow.

**When to use:** Any time SQLite is accessed from both the GTK main thread and a background thread.

```python
# In history.py — safe for call from any thread
class HistoryStore:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        db_path = self._db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db_path))
        con.execute("PRAGMA journal_mode=WAL")
        con.row_factory = sqlite3.Row
        return con

    def ensure_schema(self):
        with self._connect() as con:
            con.execute(CREATE_TABLE_SQL)
            con.execute(CREATE_IDX_SQL)

    def insert(self, entry: dict, max_entries: int = 20) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO history (entry_type, created_at, duration_sec, "
                "raw_text, processed_text, app_name, window_title) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entry['entry_type'], entry['created_at'], entry['duration_sec'],
                 entry['raw_text'], entry['processed_text'],
                 entry['app_name'], entry['window_title']),
            )
            row_id = cur.lastrowid
            # Prune oldest rows beyond max_entries
            con.execute(
                "DELETE FROM history WHERE id NOT IN "
                "(SELECT id FROM history ORDER BY created_at DESC LIMIT ?)",
                (max_entries,),
            )
            con.commit()
        return row_id

    def fetch_all(self) -> list[sqlite3.Row]:
        with self._connect() as con:
            return con.execute(
                "SELECT * FROM history ORDER BY created_at DESC"
            ).fetchall()

    def clear_all(self):
        with self._connect() as con:
            con.execute("DELETE FROM history")
            con.commit()
```

**Key decisions:**
- `with self._connect() as con` uses the context manager which auto-commits on success and auto-rolls-back on exception.
- WAL mode: set on every new connection via PRAGMA — idempotent and fast.
- Prune in the same transaction as insert to keep the DB bounded in a single atomic operation.

### Pattern 3: Gtk.ListBox Expandable Rows

**What:** Custom `Gtk.ListBoxRow` subclass holding a `compact_box` (always visible) and a `detail_box` (hidden by default). The `row-activated` signal on the `Gtk.ListBox` toggles `detail_box.set_visible()`.

**When to use:** Click-to-expand list items in GTK 4 without third-party widget libraries.

```python
class HistoryRow(Gtk.ListBoxRow):
    def __init__(self, entry: sqlite3.Row):
        super().__init__()
        self._expanded = False

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        # Compact summary (always visible)
        compact = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        compact.set_margin_start(12)
        compact.set_margin_end(12)
        compact.set_margin_top(8)
        compact.set_margin_bottom(8)
        ts_label = Gtk.Label(label=_format_timestamp(entry['created_at']))
        ts_label.set_xalign(0)
        dur_label = Gtk.Label(label=f"{entry['duration_sec']:.1f}s")
        dur_label.add_css_class("dim-label")
        preview = Gtk.Label(label=_truncate(entry['processed_text'] or '', 80))
        preview.set_hexpand(True)
        preview.set_xalign(0)
        preview.set_ellipsize(Pango.EllipsizeMode.END)
        compact.append(ts_label)
        compact.append(dur_label)
        compact.append(preview)
        outer.append(compact)

        # Detail area (hidden by default)
        self._detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._detail.set_visible(False)
        self._detail.set_margin_start(12)
        self._detail.set_margin_end(12)
        self._detail.set_margin_bottom(12)
        # ... build detail content (processed text, raw text, copy buttons) ...
        outer.append(self._detail)

    def toggle_expand(self):
        self._expanded = not self._expanded
        self._detail.set_visible(self._expanded)

# In HistoryWindow:
listbox.connect("row-activated", lambda lb, row: row.toggle_expand())
listbox.set_activate_on_single_click(True)
```

### Pattern 4: Live Updates via GLib.idle_add

**What:** The TranscriptionPipeline calls `GLib.idle_add(history_window.prepend_entry, entry_data)` after a successful run, if the history window is open.

**When to use:** Any cross-thread GTK widget update — matches the existing pattern in `TranscriptionPipeline._process()` for all other GTK side-effects.

```python
# In TranscriptionPipeline._process(), after successful paste:
if self._on_history_entry:
    GLib.idle_add(self._on_history_entry, {
        'entry_type': 'transcription',
        'created_at': started_at.isoformat(),
        'duration_sec': duration,
        'raw_text': raw_transcript,
        'processed_text': final_text.strip(),
        'app_name': window_info.get('wm_class', ''),
        'window_title': window_info.get('title', ''),
    })
```

### Pattern 5: Single-Instance Window (Focus-or-Open)

**What:** App holds `self._history_window = None`. On tray menu click, if not None call `present()`; if None, create and store.

**When to use:** All secondary windows in this codebase — matches existing `_settings` and `_debug_window` patterns in `app.py`.

```python
def _on_open_history(self, _btn=None):
    if self._history_window is None:
        self._history_window = HistoryWindow(
            application=self,
            history_store=self._history_store,
        )
        self._history_window.connect("close-request", self._on_history_closed)
    self._history_window.present()

def _on_history_closed(self, _window):
    self._history_window = None
    return False
```

### Pattern 6: Window Size Persistence

**What:** On `close-request`, call `get_default_size()` and save to config.json. On `__init__`, call `set_default_size()` with saved values.

**Source:** GTK4 official docs — `get_default_size()` is explicitly recommended for cross-session size persistence.

```python
# On __init__:
config = load_config()
w = config.get('history_window_width', 700)
h = config.get('history_window_height', 500)
self.set_default_size(w, h)

# On close-request:
def _on_close(self, _window):
    w, h = self.get_default_size()
    config = load_config()
    config['history_window_width'] = w
    config['history_window_height'] = h
    save_config(config)
    return False
```

### Pattern 7: Clipboard Copy Button

**What:** Copy button next to each transcript section copies text to the system clipboard via GTK 4's `Gdk.Display.get_default().get_clipboard().set(text)`.

**Source:** PyGObject official clipboard tutorial — `Gdk.Clipboard.set()` accepts a string directly.

```python
def _make_copy_button(text: str) -> Gtk.Button:
    btn = Gtk.Button(label="Copy")
    btn.connect("clicked", lambda _: Gdk.Display.get_default().get_clipboard().set(text))
    return btn
```

### Anti-Patterns to Avoid

- **Sharing a single sqlite3 connection across threads:** SQLite connections are not thread-safe by default. Always create a new connection per thread or per call. Do NOT set `check_same_thread=False` and share a single connection object.
- **Reading window size with `get_allocated_width()` / `get_allocated_height()`:** These return layout allocation sizes that may differ from the user-set window size. Use `get_default_size()` for persistence.
- **Using GTK widget methods directly from the background thread:** All GTK mutations (prepend row, update label) must go through `GLib.idle_add()`.
- **Deleting rows with `ORDER BY ... LIMIT` directly:** SQLite's compile-time `SQLITE_ENABLE_UPDATE_DELETE_LIMIT` may not be enabled on all systems. Use the safe subquery form: `DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY created_at DESC LIMIT ?)`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQLite connection management | Custom connection pool | Per-call `sqlite3.connect()` with context manager | The pipeline processes serially; one connection per call is sufficient and avoids pool complexity |
| Thread-safe GTK updates | Queue + polling timer | `GLib.idle_add()` | Already used throughout codebase; correct and idiomatic |
| Expandable row widget | Custom expand/collapse animation | Toggle `detail_box.set_visible()` | GTK handles relayout automatically on visibility change; no animation needed per CONTEXT.md |
| Clipboard write | subprocess xclip | `Gdk.Display.get_default().get_clipboard().set()` | In-process GTK API; no subprocess |

**Key insight:** The entire feature can be built with Python stdlib + already-imported GTK bindings. Zero new pip dependencies.

## Common Pitfalls

### Pitfall 1: Writing to SQLite from GTK Main Thread Blocking UI

**What goes wrong:** If `HistoryStore.insert()` is called directly on the GTK main thread (e.g., inside a `GLib.idle_add` callback that also does the DB write), slow disk I/O freezes the UI.
**Why it happens:** GTK is single-threaded; any blocking call on the main thread blocks rendering.
**How to avoid:** DB writes happen in `TranscriptionPipeline._process()` on the worker thread BEFORE the `GLib.idle_add` for UI update. The worker thread writes to DB, then dispatches a lightweight idle callback that only touches GTK widgets.
**Warning signs:** UI freezes briefly after each transcription.

### Pitfall 2: SQLite "database is locked" Error

**What goes wrong:** The history window reads while the pipeline worker writes, causing a lock error.
**Why it happens:** Default SQLite journal mode (`DELETE`) blocks readers during writes.
**How to avoid:** Enable WAL mode with `PRAGMA journal_mode=WAL` on every new connection. WAL allows concurrent readers and one writer.
**Warning signs:** `sqlite3.OperationalError: database is locked` in logs.

### Pitfall 3: ListBox Not Updating After Prepend

**What goes wrong:** `listbox.prepend(row)` called from a non-main thread causes silent failure or crash.
**Why it happens:** GTK widget operations are not thread-safe.
**How to avoid:** Always wrap `listbox.prepend()` and `row.show()` in `GLib.idle_add()`.
**Warning signs:** New transcriptions don't appear in the history window until it's closed and reopened.

### Pitfall 4: Window Size Drifting on Each Open

**What goes wrong:** The window grows or shrinks slightly on each open/close cycle.
**Why it happens:** Saving `get_allocated_width()` instead of `get_default_size()` captures the layout allocation which may include decorations or padding that accumulate.
**How to avoid:** Only use `get_default_size()` for saving and `set_default_size()` for restoring. Source: GTK4 official docs explicitly state this is the right method for session persistence.
**Warning signs:** Window is slightly different size each time it opens.

### Pitfall 5: Schema Lock-In Preventing Phase 6 Extension

**What goes wrong:** Phase 5 implements a rigid schema (e.g., a single table with only transcription-specific columns, no discriminator) that makes Phase 6's conversation row type require a full migration.
**Why it happens:** Not designing for the known future extension stated in CONTEXT.md.
**How to avoid:** Include `entry_type TEXT NOT NULL DEFAULT 'transcription'` and `extra_json TEXT` from the start. Phase 6 inserts `entry_type='conversation'` rows with additional data in `extra_json`.
**Warning signs:** Phase 6 researcher notes schema migration is required.

### Pitfall 6: Clear History Leaves extra_json / audio Temp Files

**What goes wrong:** "Clear Temp Audio Files" button only deletes WAV files in the failed/ dir but not audio artifacts from conversation mode (Phase 6).
**Why it happens:** Phase 5 only knows about `~/.local/share/linux-speech-flow/failed/` as the temp audio location.
**How to avoid:** The "Clear Temp Audio Files" in Phase 5 only clears `failed/*.wav`. Its scope is limited. Document this clearly so Phase 6 extends it.

## Code Examples

### Complete HistoryStore skeleton

```python
# Source: Python docs sqlite3 + official GTK4 WAL guidance
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "linux-speech-flow" / "history.db"

CREATE_TABLE_SQL = """
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

CREATE_IDX_SQL = """
CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC)
"""

class HistoryStore:
    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self.ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self._db_path))
        con.execute("PRAGMA journal_mode=WAL")
        con.row_factory = sqlite3.Row
        return con

    def ensure_schema(self):
        with self._connect() as con:
            con.execute(CREATE_TABLE_SQL)
            con.execute(CREATE_IDX_SQL)

    def insert(self, entry: dict, max_entries: int = 20) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO history "
                "(entry_type, created_at, duration_sec, raw_text, "
                "processed_text, app_name, window_title) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.get('entry_type', 'transcription'),
                    entry['created_at'],
                    entry.get('duration_sec'),
                    entry.get('raw_text', ''),
                    entry.get('processed_text', ''),
                    entry.get('app_name', ''),
                    entry.get('window_title', ''),
                ),
            )
            row_id = cur.lastrowid
            con.execute(
                "DELETE FROM history WHERE id NOT IN "
                "(SELECT id FROM history ORDER BY created_at DESC LIMIT ?)",
                (max_entries,),
            )
        return row_id

    def fetch_all(self) -> list:
        with self._connect() as con:
            return con.execute(
                "SELECT * FROM history ORDER BY created_at DESC"
            ).fetchall()

    def clear_all(self):
        with self._connect() as con:
            con.execute("DELETE FROM history")
```

### Clipboard copy in GTK 4 (Python)

```python
# Source: PyGObject official clipboard tutorial
import gi
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

def copy_to_clipboard(text: str):
    Gdk.Display.get_default().get_clipboard().set(text)
```

### Wiring history write into TranscriptionPipeline._process()

```python
# In TranscriptionPipeline.__init__:
self._on_history_entry = None  # set by App after HistoryStore created

# In _process(), capture start time at top:
started_at = datetime.utcnow()

# After successful paste (before _on_paste_complete idle_add):
duration = (datetime.utcnow() - started_at).total_seconds()
if self._history_store:
    max_entries = config.get('history_max_entries', 20)
    self._history_store.insert({
        'entry_type': 'transcription',
        'created_at': started_at.isoformat(),
        'duration_sec': duration,
        'raw_text': raw_transcript,
        'processed_text': final_text.strip(),
        'app_name': window_info.get('wm_class', ''),
        'window_title': window_info.get('title', ''),
    }, max_entries=max_entries)
    if self._on_history_entry:
        GLib.idle_add(self._on_history_entry, {...})
```

### config.py additions

```python
# New keys to add to DEFAULT_CONFIG:
"history_max_entries": 20,
"history_window_width": 700,
"history_window_height": 500,
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gtk.Clipboard (GTK 3) | Gdk.Display.get_default().get_clipboard() + .set() (GTK 4) | GTK 4.0 release | Gtk.Clipboard no longer exists in GTK 4; must use GDK layer |
| get_allocated_width() for size persistence | get_default_size() | GTK 4 docs explicit recommendation | Prevents window drift |

**Deprecated/outdated:**
- `Gtk.Clipboard`: Removed in GTK 4. Use `Gdk.Display.get_default().get_clipboard()`.
- `Gtk.Dialog`: Deprecated since GTK 4.10 — already noted in project decisions. For confirmation dialogs, use `Gtk.Window` with `set_modal(True)`. This matches the existing pattern in Phase 3 (`reprocess_dialog.py`).

## Open Questions

1. **`started_at` capture point in `_process()`**
   - What we know: `_process()` starts after potentially waiting in the queue; the timestamp should reflect when recording ended, not when processing started.
   - What's unclear: Should `created_at` be the recording-end time (captured in `submit()`) or the processing-start time (inside `_process()`)?
   - Recommendation: Capture `started_at` in `submit()` alongside `window_info` capture and pass it through the queue tuple. This makes the timestamp reflect "when the user finished speaking."

2. **"Clear Temp Audio Files" scope**
   - What we know: Current temp audio is in `~/.local/share/linux-speech-flow/failed/`. The history DB is in the same parent dir.
   - What's unclear: Should "Clear Temp Audio Files" also vacuum the SQLite DB? Or is that a separate concern?
   - Recommendation: Keep them separate. "Clear Temp Audio Files" = `failed/*.wav` only. "Clear All History" = DB rows only. VACUUM can be called after Clear All History as a one-liner.

3. **Empty state hotkey display**
   - What we know: The configured hotkey is stored in config.json (currently hardcoded F9 with no user-facing config key yet — Phase 7 adds this).
   - What's unclear: There is no `hotkey_record` key in `DEFAULT_CONFIG` yet.
   - Recommendation: Read from config; if no key exists, display "F9" as the hardcoded default. Phase 7 will add the actual config key.

## Sources

### Primary (HIGH confidence)

- Python 3.x stdlib sqlite3 docs (https://docs.python.org/3/library/sqlite3.html) — schema creation, INSERT, DELETE subquery, WAL mode, context manager pattern
- GTK4 official docs Gtk.ListBoxRow (https://docs.gtk.org/gtk4/class.ListBoxRow.html) — activatable property, row-activated signal, toggle visibility pattern
- GTK4 official docs Gtk.Window (https://docs.gtk.org/gtk4/class.Window.html) — get_default_size, set_default_size, close-request signal
- PyGObject clipboard tutorial (https://pygobject.gnome.org/tutorials/gtk4/clipboard.html) — Gdk.Display.get_default().get_clipboard().set()
- GTK4 save state tutorial (https://developer.gnome.org/documentation/tutorials/save-state.html) — window persistence pattern
- Codebase inspection (transcription.py, app.py, settings.py, config.py, debug_window.py) — threading patterns, GLib.idle_add usage, single-instance window pattern, DEFAULT_CONFIG structure

### Secondary (MEDIUM confidence)

- SQLite official threading docs (https://sqlite.org/threadsafe.html) — WAL mode + per-thread connections confirmed safe
- iifx.dev SQLite concurrency article — WAL mode allows concurrent readers and one writer

### Tertiary (LOW confidence)

- None — all critical claims verified with primary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — sqlite3 stdlib confirmed present (Python 3.10, SQLite 3.37.2); GTK 4.6.9 confirmed installed; no new deps required
- Architecture: HIGH — patterns derived from official GTK4/Python docs + direct codebase inspection matching existing project patterns
- Pitfalls: HIGH — threading pitfalls from official SQLite docs; GTK main-thread rule from PyGObject; window size drift from GTK4 docs explicit warning

**Research date:** 2026-02-21
**Valid until:** Stable stack — valid for 6 months (sqlite3 stdlib; GTK 4.6.x system package)
