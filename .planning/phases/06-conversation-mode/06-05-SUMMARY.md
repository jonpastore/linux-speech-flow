---
phase: 06-conversation-mode
plan: 05
subsystem: ui
tags: [gtk4, gtk-paned, conversation-viewer, file-browser, two-panel]

# Dependency graph
requires:
  - phase: 06-conversation-mode
    provides: conv_save_dir config key, conv_viewer_width/height defaults
  - phase: 06-03
    provides: coalesce_file() that writes conversation .txt files with Date/Duration/Chunks/Models header
provides:
  - ConversationViewer Gtk.ApplicationWindow: two-panel file browser for saved conversations
  - _parse_conv_metadata(): reads first 6 header lines from conversation .txt files
affects: [06-06, app.py integration, hotkey handler for showing conversation viewer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GTK4 Paned API: set_start_child/set_end_child (not GTK3 pack1/pack2)"
    - "Fresh directory scan on window open — no cached paths, handles renames"
    - "Closure capture via default argument (p=fp) for button lambda in listbox rows"

key-files:
  created:
    - src/linux_speech_flow/conversation_viewer.py
  modified: []

key-decisions:
  - "Paned divider fixed at 280px via set_position(280) with set_resize_start_child(False)"
  - "Title derived from filename: split on first underscore, replace hyphens with spaces"
  - "Ellipsize mode set via integer 3 (Pango.EllipsizeMode.END) to avoid Pango import"
  - "on_continue_qa button only rendered if callback is non-None (optional feature)"

patterns-established:
  - "Placeholder label row appended when directory missing or empty — consistent with HistoryWindow pattern"

requirements-completed: [CONV-04]

# Metrics
duration: 1min
completed: 2026-02-21
---

# Phase 6 Plan 05: ConversationViewer Summary

**Read-only two-panel GTK4 conversation browser with Paned layout, filename-derived titles, header metadata parsing, and optional Continue Q&A callback per row**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-21T18:19:24Z
- **Completed:** 2026-02-21T18:20:31Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- ConversationViewer Gtk.ApplicationWindow with Gtk.Paned HORIZONTAL layout (left list 280px, right preview)
- _load_conversations() scans conv_save_dir fresh on each open, sorted by mtime descending
- Each list row: title from filename stem, date/duration subtitle, optional "Continue Q&A" button
- Preview pane: read-only Gtk.TextView with word wrap shows full file content on row selection
- _parse_conv_metadata() extracts Date/Duration/Chunks/Models from first 6 header lines
- Graceful placeholder when conversation directory is missing or contains no .txt files

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement ConversationViewer** - `9ab438b` (feat)

**Plan metadata:** (included in docs commit below)

## Files Created/Modified
- `src/linux_speech_flow/conversation_viewer.py` - ConversationViewer window and _parse_conv_metadata helper

## Decisions Made
- Paned divider set to 280px with set_resize_start_child(False) so left panel stays fixed and right panel expands on resize
- Title derived from filename: split stem on first underscore, replace remaining hyphens with spaces; falls back to full stem if no underscore
- Pango.EllipsizeMode.END set as integer 3 rather than importing Pango separately (matches pattern where Pango not already imported)
- on_continue_qa button only added to rows if the callback is non-None — viewer works standalone without Q&A feature

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ConversationViewer importable and GTK4 Paned API verified
- Ready for App.py integration: open viewer via hotkey or menu, pass on_continue_qa callback to re-open Q&A window for saved conversation
- CONV-04 requirement satisfied

---
*Phase: 06-conversation-mode*
*Completed: 2026-02-21*
