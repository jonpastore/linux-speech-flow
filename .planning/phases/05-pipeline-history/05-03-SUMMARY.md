---
phase: 05-pipeline-history
plan: "03"
subsystem: integration
tags: [gtk4, sqlite, history, transcription-pipeline, tray-menu, settings]

requires:
  - phase: 05-01
    provides: HistoryStore with insert(), fetch_all(), clear_all(), per-call connections
  - phase: 05-02
    provides: HistoryWindow with prepend_entry() for live updates, GTK4 ListBox viewer

provides:
  - End-to-end history wiring: WAV -> transcribe -> DB insert (worker thread) -> GLib.idle_add -> HistoryWindow.prepend_entry() (main thread)
  - TranscriptionPipeline accepts history_store and on_history_entry params
  - TrayManager has 'Transcription History' menu item opening single-instance HistoryWindow
  - Settings Maintenance section: history_max_entries spinner, Clear All History dialog, Clear Temp Audio Files

affects:
  - 06-conversation-mode (HistoryWindow live update pattern reusable for conversation entries)

tech-stack:
  added: []
  patterns:
    - Worker-thread DB write + GLib.idle_add UI dispatch: _history_store.insert() on worker thread, then GLib.idle_add(self._on_history_entry, entry_dict) for GTK update
    - Single-instance window gate: None check + connect close-request to null out reference
    - Maintenance confirmation dialog: Gtk.Window(modal=True) + set_transient_for(self) — no Gtk.Dialog (deprecated GTK 4.10)

key-files:
  created: []
  modified:
    - src/linux_speech_flow/transcription.py
    - src/linux_speech_flow/app.py
    - src/linux_speech_flow/tray.py
    - src/linux_speech_flow/settings.py

key-decisions:
  - "HistoryStore.insert() called on worker thread inside _process() before GLib.idle_add — DB write never on GTK main thread"
  - "started_at captured at top of _process() before any API calls — measures total pipeline duration including Whisper + LLM"
  - "history_max_entries read from config per-call in _process() — always uses current setting without restart"
  - "Settings Maintenance section uses HistoryStore() fresh instance for clear_all() — matches per-call connection pattern established in Phase 05-01"

requirements-completed: [HIST-01, HIST-02, HIST-03]

duration: 2min
completed: 2026-02-21
---

# Phase 5 Plan 03: Pipeline History Wiring Summary

**Full history pipeline: worker-thread SQLite insert after paste, live HistoryWindow update via GLib.idle_add, tray menu item, and Settings Maintenance section with max-entries spinner and clear buttons**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-21T15:37:21Z
- **Completed:** 2026-02-21T15:39:34Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Wired HistoryStore into TranscriptionPipeline: `started_at` captured at process start, DB insert on worker thread, `GLib.idle_add` dispatches entry dict to GTK thread for live window update
- App.py now initializes `HistoryStore`, passes it to pipeline, implements single-instance `_on_open_history()` with `present()` guard and `_on_history_entry_received()` callback
- TrayManager gains `on_history` param; "Transcription History" menu item inserted before "Settings" in tray menu
- Settings adds Maintenance section: history_max_entries SpinButton (range 5–500), "Clear All History" with confirmation dialog, "Clear Temp Audio Files" — all persisted via `_on_save()`

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire HistoryStore into TranscriptionPipeline | f61dc92 | src/linux_speech_flow/transcription.py |
| 2 | Wire HistoryWindow into app.py + tray menu + Settings Maintenance | 6ccad14 | src/linux_speech_flow/app.py, tray.py, settings.py |

## Files Created/Modified

- `src/linux_speech_flow/transcription.py` - Added history_store/on_history_entry params; started_at capture; DB insert + GLib.idle_add dispatch after successful paste
- `src/linux_speech_flow/app.py` - Imports HistoryStore/HistoryWindow; _history_store init in do_startup; _on_open_history, _on_history_closed, _on_history_entry_received methods
- `src/linux_speech_flow/tray.py` - on_history param; 'Transcription History' menu item prepended to menu
- `src/linux_speech_flow/settings.py` - Imports HistoryStore/FAILED_DIR; Maintenance section with spinner, clear buttons, confirmation dialog; history_max_entries saved in _on_save()

## Decisions Made

- `_history_store.insert()` runs on the worker thread inside `_process()`, not inside `GLib.idle_add` — keeps GTK thread free of blocking DB calls
- `started_at = datetime.utcnow()` captured before any Whisper/LLM API calls — accurately measures total pipeline duration
- `history_max_entries` read from `config` dict already passed to `_process()` — uses current config value without needing a separate config load
- Settings `_on_clear_all_history` creates `HistoryStore()` fresh — consistent with per-call connection pattern; no shared state needed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 5 (Pipeline History) is fully complete: DB store, GTK viewer, pipeline wiring, tray menu, and Settings Maintenance all done
- HIST-01, HIST-02, HIST-03 requirements satisfied
- Phase 6 (Conversation Mode) can build on the entry_type column in history.db and the live prepend_entry() pattern in HistoryWindow

## Self-Check: PASSED

- FOUND: src/linux_speech_flow/transcription.py (modified)
- FOUND: src/linux_speech_flow/app.py (modified)
- FOUND: src/linux_speech_flow/tray.py (modified)
- FOUND: src/linux_speech_flow/settings.py (modified)
- FOUND commit f61dc92 (feat(05-03): wire HistoryStore into TranscriptionPipeline)
- FOUND commit 6ccad14 (feat(05-03): wire HistoryWindow into app.py, tray menu, and settings)

---
*Phase: 05-pipeline-history*
*Completed: 2026-02-21*
