---
phase: 06-conversation-mode
plan: 04
subsystem: ui
tags: [gtk4, glib, threading, conversation-mode, state-machine, silence-detection]

requires:
  - phase: 06-03
    provides: ConversationPipeline transcribe_chunk and multi-model analysis engine
  - phase: 06-02
    provides: ConversationRecorder chunked audio delivery via on_chunk_ready
  - phase: 06-01
    provides: F11/F12 hotkey wiring and conv_* config defaults

provides:
  - ConversationManager session state machine (start_session, stop_session, toggle_feedback)
  - ConversationStatusWindow live GTK status display (elapsed timer + chunk count)
  - Session-level silence timer cascade: 180s warn modal, 300s auto-stop, 4hr hard limit
  - Per-chunk transcription dispatch to daemon threads with GTK-thread result delivery

affects: [06-05, app.py integration, hotkey wiring for F11/F12]

tech-stack:
  added: []
  patterns:
    - GLib.timeout_add_seconds for silence timer cascade with source_remove on chunk arrival
    - GLib.idle_add for all GTK operations called from daemon threads
    - Gtk.Window(modal=True) for dialogs (not Gtk.Dialog, deprecated GTK 4.10)
    - daemon=True threads for Whisper transcription isolation
    - 500ms GLib.timeout_add defer in stop_session to allow last chunk idle_add to fire

key-files:
  created:
    - src/linux_speech_flow/conversation_manager.py
    - src/linux_speech_flow/conversation_status.py
  modified: []

key-decisions:
  - "ConversationManager imports ConversationStatusWindow lazily inside _show_status_window to avoid circular import risk"
  - "silence_stop timer created inside _on_silence_warn callback (not pre-created) — ensures timer only starts after warn fires"
  - "stop_session defers _finish_session 500ms via GLib.timeout_add to allow last chunk GLib.idle_add to flush before transcript assembly"
  - "Gtk.Window(modal=True) used for silence warning dialog — matches project pattern avoiding deprecated Gtk.Dialog"

patterns-established:
  - "Session-level silence timers: cancel+recreate on every on_chunk_ready; only fire when no chunk arrives for N seconds"
  - "GTK thread safety: all UI updates via GLib.idle_add from worker threads; all GLib timers created/cancelled on main thread"

requirements-completed: [CONV-01, CONV-02]

duration: 2min
completed: 2026-02-21
---

# Phase 06 Plan 04: ConversationManager and ConversationStatusWindow Summary

**GTK session state machine with silence timer cascade (180s warn / 300s stop / 4hr hard limit) and live status window with per-second elapsed display**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T18:16:00Z
- **Completed:** 2026-02-21T18:17:38Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- ConversationStatusWindow: Gtk.ApplicationWindow with per-second elapsed timer, chunk count display, set_deletable(False) during recording
- ConversationManager: full session state machine connecting ConversationRecorder and ConversationPipeline
- Session-level silence detection: timers reset on every on_chunk_ready, 180s warn modal, 300s auto-stop, 4hr hard limit
- Per-chunk Whisper transcription in daemon threads with GLib.idle_add result delivery to GTK main thread
- stop_session assembles full transcript and fires on_session_complete with metadata dict (date, duration, chunk_count, models_used)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement ConversationStatusWindow** - `0d82fed` (feat)
2. **Task 2: Implement ConversationManager** - `da740aa` (feat)

## Files Created/Modified
- `src/linux_speech_flow/conversation_status.py` - Gtk.ApplicationWindow live status display with elapsed timer and chunk count
- `src/linux_speech_flow/conversation_manager.py` - Session state machine: recorder lifecycle, silence timers, chunk transcription dispatch, session completion

## Decisions Made
- ConversationStatusWindow imported lazily inside _show_status_window to avoid potential circular import
- Silence stop timer created inside _on_silence_warn callback (not pre-created) — only starts after warn actually fires
- stop_session defers _finish_session 500ms via GLib.timeout_add so last chunk GLib.idle_add can flush before transcript assembly
- Gtk.Window(modal=True) used for silence warning dialog — consistent with project pattern avoiding deprecated Gtk.Dialog (GTK 4.10)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- ConversationManager ready for App.py integration (plan 06-05)
- F11 hotkey should call manager.start_session() / manager.stop_session()
- F12 hotkey should call manager.toggle_feedback()
- on_session_complete callback will trigger post-stop analysis dialog (plan 06-05)

---
*Phase: 06-conversation-mode*
*Completed: 2026-02-21*
