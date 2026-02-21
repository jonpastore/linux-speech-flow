---
phase: 05-pipeline-history
plan: "01"
subsystem: database
tags: [sqlite, history, persistence, wal, python]

requires:
  - phase: 03-transcription-and-text-injection
    provides: transcription pipeline that produces raw_text and processed_text to store
  - phase: 01-foundation-and-configuration
    provides: config.py DEFAULT_CONFIG dict-merge pattern for backfilling new keys

provides:
  - HistoryStore class with SQLite persistence at ~/.local/share/linux-speech-flow/history.db
  - Schema extensible for Phase 6 conversation rows via entry_type + extra_json columns
  - Automatic pruning to N most-recent entries on every insert
  - DEFAULT_CONFIG keys: history_max_entries (20), history_window_width (700), history_window_height (500)

affects:
  - 05-02 (history viewer UI will import HistoryStore and use history_window_* config)
  - 06-conversation-mode (entry_type column allows storing conversation rows alongside transcription rows)

tech-stack:
  added: [sqlite3 (stdlib)]
  patterns:
    - Per-call connection pattern (new connection per HistoryStore method — thread-safe by design)
    - WAL mode set on every connection via PRAGMA journal_mode=WAL
    - Safe subquery prune (DELETE WHERE id NOT IN SELECT) avoids SQLITE_ENABLE_UPDATE_DELETE_LIMIT dependency

key-files:
  created: [src/linux_speech_flow/history.py]
  modified: [src/linux_speech_flow/config.py]

key-decisions:
  - "Per-call connection (not shared): HistoryStore._connect() called fresh in each method — no locking needed, safe from any thread"
  - "Safe subquery prune form: DELETE FROM history WHERE id NOT IN (SELECT id ... LIMIT ?) avoids optional SQLite compile flag dependency"
  - "entry_type + extra_json columns added now for Phase 6 extensibility without schema migration"
  - "WAL mode: set on every connection open; ensures concurrent reads don't block writes from background recording thread"

patterns-established:
  - "Phase 5 config keys: three new history_* keys added to DEFAULT_CONFIG; existing dict-merge backfill in load_config() handles existing user configs automatically"

requirements-completed: [HIST-01, HIST-02]

duration: 1min
completed: 2026-02-21
---

# Phase 5 Plan 01: Pipeline History Summary

**SQLite HistoryStore with WAL mode, per-call connections, auto-pruning, and Phase-6-extensible schema (entry_type + extra_json)**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-02-21T15:30:42Z
- **Completed:** 2026-02-21T15:31:33Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `history.py` with HistoryStore class: schema creation, insert+prune, fetch_all, clear_all (82 lines)
- Schema includes `entry_type` and `extra_json` columns for Phase 6 conversation-mode rows
- Prune on every insert using safe subquery form (no SQLITE_ENABLE_UPDATE_DELETE_LIMIT dependency)
- Added three history config defaults to DEFAULT_CONFIG (max_entries=20, window_width=700, window_height=500)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create HistoryStore in history.py** - `4301a54` (feat)
2. **Task 2: Add history config defaults to DEFAULT_CONFIG** - `611175b` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `src/linux_speech_flow/history.py` - HistoryStore class with SQLite persistence, WAL mode, per-call connections, prune-on-insert
- `src/linux_speech_flow/config.py` - Added history_max_entries, history_window_width, history_window_height to DEFAULT_CONFIG

## Decisions Made

- Per-call connection pattern: each HistoryStore method calls `_connect()` independently — no shared state, thread-safe without locks
- Safe prune subquery: `DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY created_at DESC LIMIT ?)` avoids dependence on optional SQLite `SQLITE_ENABLE_UPDATE_DELETE_LIMIT` compile flag
- WAL mode on every connection open: ensures background recording thread can write while viewer reads
- `entry_type` defaulting to `'transcription'` and `extra_json` TEXT column added now to avoid Phase 6 schema migration

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- HistoryStore is ready for Plan 02 to wire into the transcription pipeline (`app.py` calling `store.insert()` after each recording completes)
- history_window_* config defaults are ready for the history viewer UI
- No blockers

## Self-Check: PASSED

- FOUND: src/linux_speech_flow/history.py
- FOUND: src/linux_speech_flow/config.py
- FOUND: .planning/phases/05-pipeline-history/05-01-SUMMARY.md
- FOUND commit 4301a54 (feat: HistoryStore)
- FOUND commit 611175b (feat: config defaults)

---
*Phase: 05-pipeline-history*
*Completed: 2026-02-21*
