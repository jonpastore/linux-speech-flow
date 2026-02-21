---
phase: 06-conversation-mode
plan: 07
subsystem: ui
tags: [gtk4, conversation-mode, conversation-manager, settings, tray, hotkeys]

requires:
  - phase: 06-01
    provides: HotkeyManager F11/F12 conversation callbacks
  - phase: 06-02
    provides: ConversationRecorder
  - phase: 06-03
    provides: ConversationPipeline, conv_filename, coalesce_file
  - phase: 06-04
    provides: ConversationManager, ConversationStatusWindow
  - phase: 06-05
    provides: ConversationViewer
  - phase: 06-06
    provides: ConversationDialog, ConversationQAWindow
provides:
  - "ConversationManager wired into App.do_startup() with F11/F12 hotkey callbacks"
  - "ConversationDialog opened on session complete via _on_conv_session_complete"
  - "ConversationQAWindow launched from _on_conv_dialog_submit with background analyze thread"
  - "Conversation History tray menu item opening ConversationViewer"
  - "Settings Conversation Mode section: Grok/Gemini API keys, save dir, feedback mode, max Q&A, auto-analyze, default prompt, qualifying questions editor"
affects: [07-hotkey-customization, 08-slack-integration]

tech-stack:
  added: []
  patterns:
    - "ConversationManager lifecycle wired via App.__init__ instance variables and do_startup() instantiation"
    - "Background analyze thread with GLib.idle_add(_open_qa) for GTK-safe Q&A window launch"
    - "Lazy lambda for on_tray_state to avoid forward reference to self._tray at instantiation time"

key-files:
  created: []
  modified:
    - src/linux_speech_flow/app.py
    - src/linux_speech_flow/tray.py
    - src/linux_speech_flow/settings.py

key-decisions:
  - "ConversationManager instantiated before TrayManager in do_startup() — on_tray_state uses lambda to defer self._tray lookup until call time, avoiding forward reference issue"
  - "Conversation History tray item added as second item (after Transcription History) to maintain logical grouping with existing history item"
  - "Settings dirty tracking extended to all Phase 6 widgets so unsaved-changes dialog triggers correctly"

patterns-established:
  - "Conversation callbacks follow same pattern as recording callbacks: _on_conv_start/stop/feedback_toggle delegate to manager"
  - "Viewer singleton pattern: _conv_viewer instance cached, close-request sets to None, reuse on re-open"

requirements-completed: [CONV-01, CONV-02, CONV-03, CONV-04, CONV-05]

duration: 2min
completed: 2026-02-21
---

# Phase 06 Plan 07: Wire Conversation Mode into App Summary

**ConversationManager wired into App via F11/F12 hotkeys, session-complete dialog chain, tray Conversation History item, and full Phase 6 Settings section with API keys, save location, and qualifying questions editor**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T18:27:01Z
- **Completed:** 2026-02-21T18:29:17Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Wired ConversationManager into App.do_startup(): instantiated with session_complete and tray_state callbacks, and three F11/F12 hotkey methods passed to HotkeyManager
- Implemented full session-complete flow: ConversationDialog opened from _on_conv_session_complete, dialog submit runs analyze in background thread and opens ConversationQAWindow, inject_to_window supported
- Added Conversation History tray menu item (second in menu) opening ConversationViewer singleton, with continue-QA callback plumbing
- Added complete Conversation Mode Settings section: Grok API key, Gemini API key, save location, feedback mode combo, max Q&A spin, auto-analyze checkbox, default prompt textarea, qualifying questions editor
- Extended dirty tracking to all new Settings widgets for correct unsaved-changes dialog behavior
- Shutdown cleanup: stops ConversationRecorder in do_shutdown() if active

## Task Commits

1. **Task 1: Wire ConversationManager into App and add tray menu item** - `b5e8620` (feat)
2. **Task 2: Add Phase 6 Settings section** - `fe67ac0` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified
- `src/linux_speech_flow/app.py` - Added ConversationManager import and __init__ vars, updated do_startup() wiring, added 7 new methods (_on_conv_start, _on_conv_stop, _on_conv_feedback_toggle, _on_conv_session_complete, _on_conv_dialog_submit, _on_open_conv_viewer/_closed, _on_conv_continue_qa), updated do_shutdown()
- `src/linux_speech_flow/tray.py` - Added on_conv_history parameter to TrayManager.__init__(); added Conversation History menu item after Transcription History
- `src/linux_speech_flow/settings.py` - Added full Conversation Mode section to __init__() (separator, title, Grok key, Gemini key, save dir, feedback combo, Q&A spin, auto-analyze check, prompt textarea, qualifying questions textarea); added Phase 6 save logic to _on_save(); extended dirty tracking in _connect_change_signals()

## Decisions Made
- Used lazy lambda `lambda state: self._tray.set_state(state) if self._tray else None` for on_tray_state to avoid forward reference since ConversationManager is instantiated before TrayManager
- Conversation History inserted as second tray item (after Transcription History) so both history items are grouped at top of menu
- Settings dirty tracking explicitly extended to all 10 new widgets to match existing behavior pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required (API keys entered via Settings UI).

## Next Phase Readiness
- Phase 6 Conversation Mode is now fully wired end-to-end: F11 starts session, F12 toggles feedback, F11 again stops and opens analysis dialog, dialog submits to Q&A window, Conversation History in tray opens viewer
- All CONV-01 through CONV-05 requirements satisfied
- Phase 7 (Hotkey Customization) can proceed: conv_hotkey_start (f11) and conv_hotkey_feedback (f12) are configurable per existing config keys

---
*Phase: 06-conversation-mode*
*Completed: 2026-02-21*

## Self-Check: PASSED

- FOUND: src/linux_speech_flow/app.py
- FOUND: src/linux_speech_flow/tray.py
- FOUND: src/linux_speech_flow/settings.py
- FOUND: .planning/phases/06-conversation-mode/06-07-SUMMARY.md
- FOUND commit: b5e8620 (Task 1)
- FOUND commit: fe67ac0 (Task 2)
