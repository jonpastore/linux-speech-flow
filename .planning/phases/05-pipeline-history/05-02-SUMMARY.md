---
phase: 05-pipeline-history
plan: "02"
subsystem: ui
tags: [gtk4, history-viewer, listbox, expandable-rows, clipboard, config-persistence]

requires:
  - phase: 05-01
    provides: HistoryStore with fetch_all(), clear_all(), and history_window_* config defaults

provides:
  - HistoryWindow (Gtk.ApplicationWindow) with Gtk.ListBox expandable row viewer
  - HistoryRow (Gtk.ListBoxRow) with compact summary and toggle-expand detail
  - prepend_entry() method for GLib.idle_add live updates from pipeline thread
  - Window size persisted across opens via history_window_width/height config keys

affects:
  - 05-03 (app.py will import HistoryWindow and wire into tray menu)
  - 06-conversation-mode (HistoryRow handles both dict and sqlite3.Row via [] access)

tech-stack:
  added: []
  patterns:
    - Gtk.ListBoxRow subclass with NONE selection mode and row-activated signal for self-managed expand
    - Gdk.Display.get_default().get_clipboard().set(t) with closure capture (t=text) prevents late binding
    - Gtk.Window(modal=True) + set_transient_for() for confirmation dialogs (not deprecated Gtk.Dialog)
    - Gtk.CssProvider applied to raw transcript background box for muted visual differentiation
    - GLib.idle_add contract: prepend_entry returns False to avoid re-invocation

key-files:
  created: [src/linux_speech_flow/history_window.py]
  modified: []

key-decisions:
  - "Gtk.ListBox selection_mode=NONE with row-activated toggle: rows manage own expand state, no selection highlight"
  - "Closure capture (t=text) in Copy button lambda prevents late-binding bug common with loop-created callbacks"
  - "Gtk.Window(modal=True) not Gtk.Dialog: matches project pattern established in reprocess_dialog.py (GTK 4.10 deprecation)"
  - "prepend_entry removes Gtk.Label empty-state child by isinstance check before inserting first HistoryRow"

metrics:
  duration: 1min
  completed: 2026-02-21
  tasks: 1
  files_created: 1
  files_modified: 0
---

# Phase 5 Plan 02: History Window Summary

**GTK4 HistoryWindow with expandable HistoryRow widgets, Gdk clipboard copy, config-persisted size, and live prepend_entry() for pipeline updates**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-02-21T15:33:48Z
- **Completed:** 2026-02-21T15:35:01Z
- **Tasks:** 1
- **Files created:** 1

## Accomplishments

- Created `history_window.py` (263 lines) with HistoryWindow and HistoryRow GTK4 classes
- HistoryWindow: scrollable Gtk.ListBox, header with "Transcription History" + "Clear All History", footer with "Clear Temp Audio Files"
- HistoryRow: compact row (timestamp | duration | truncated preview), expand-on-click detail with processed text, raw transcript, app/window context
- Copy buttons use `Gdk.Display.get_default().get_clipboard().set(t)` with `t=text` closure capture
- Empty state reads configured hotkey from `load_config().get('hotkey_record', 'F9')`
- Window size saved to config on `close-request` via `get_default_size()`, restored on open via `set_default_size()`
- `prepend_entry()` removes empty-state label if present, creates HistoryRow from dict, prepends to listbox, returns False (GLib.idle_add contract)
- Clear All History uses `Gtk.Window(modal=True)` confirmation dialog with Cancel + Clear (destructive-action class)
- Clear Temp Audio Files deletes all `~/.local/share/linux-speech-flow/failed/*.wav` and shows count in footer status label

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create HistoryWindow and HistoryRow in history_window.py | 82c18d5 | src/linux_speech_flow/history_window.py |

## Files Created/Modified

- `src/linux_speech_flow/history_window.py` - HistoryWindow and HistoryRow GTK4 classes (263 lines)

## Decisions Made

- `Gtk.ListBox` selection mode set to NONE; `row-activated` signal used so each row's `toggle_expand()` handles its own expand/collapse without GTK selection state interfering
- Copy button lambdas use `t=text` closure capture (not bare `text`) to prevent the classic Python late-binding bug with loop-created callbacks
- `Gtk.Window(modal=True)` + `set_transient_for(self)` for confirmation dialog, following pattern from `reprocess_dialog.py` (Gtk.Dialog deprecated in GTK 4.10)
- `prepend_entry` checks `isinstance(first, Gtk.Label)` to identify and remove the empty-state label when first real entry arrives

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- HistoryWindow is ready for Plan 03 to wire into app.py (tray menu "Show History" item)
- `prepend_entry()` is ready for the pipeline to call via `GLib.idle_add(self._history_window.prepend_entry, entry)` after each transcription
- No blockers

## Self-Check: PASSED

- FOUND: src/linux_speech_flow/history_window.py
- FOUND commit 82c18d5 (feat(05-02): HistoryWindow and HistoryRow)

---
*Phase: 05-pipeline-history*
*Completed: 2026-02-21*
