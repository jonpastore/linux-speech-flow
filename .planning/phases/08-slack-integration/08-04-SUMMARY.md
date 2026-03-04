---
phase: 08-slack-integration
plan: 04
subsystem: ui
tags: [slack, huddle, block-kit, tray, app-wiring, conversation-pipeline]

# Dependency graph
requires:
  - phase: 08-01
    provides: SlackManager with post_message and upload_file
  - phase: 08-02
    provides: HuddleManager session orchestration, HuddleRecorder, HuddleStatusWindow
  - phase: 08-03
    provides: SlackSocket daemon thread for huddle event detection
provides:
  - HuddleManager + SlackManager + SlackSocket wired into app.py do_startup()
  - Ctrl+Alt+H hotkey triggers huddle start/stop via HotkeyManager callbacks
  - SlackSocket started per workspace with _on_huddle_event_detected and _on_huddle_end_detected
  - Auto-detect dispatch: 'always' starts immediately, 'prompt' shows notification, 'manual' ignores
  - channel_id fallback to config when event yields empty string
  - _on_huddle_end_detected auto-stops session (SLACK-05)
  - Start/Stop Huddle Recording dynamic tray menu item
  - post_huddle_results: Block Kit message + .md file upload to Slack
affects: [09-packaging, any future Slack feature plans]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - _on_huddle_dialog_submit reuses conv pipeline + on_finalised -> Slack post wiring
    - post_huddle_results runs on background thread with GLib.idle_add for GTK notifications
    - _build_huddle_result_blocks as @staticmethod producing valid Slack Block Kit list

key-files:
  created: []
  modified:
    - src/linux_speech_flow/app.py
    - src/linux_speech_flow/tray.py
    - src/linux_speech_flow/huddle_manager.py

key-decisions:
  - "_on_huddle_dialog_submit wraps ConversationDialog on_submit: adapts existing 10-arg submit contract for huddle Slack posting instead of rewriting with a new on_complete signature"
  - "post_huddle_results only posts/uploads; local file save is caller responsibility (app.py _on_huddle_dialog_submit)"
  - "_on_huddle_toggle_tray uses HuddleManager.is_active() not private HotkeyManager state — keeps tray logic independent of hotkey state machine"
  - "SlackSocket loop over workspaces in do_startup() handles zero-workspace case gracefully with no sockets started"

patterns-established:
  - "Huddle result flow: ConversationDialog submit -> pipeline.analyze -> QA window -> on_finalised -> post_huddle_results (background thread)"
  - "GLib.idle_add(lambda: send_notification(...)) pattern for background-thread GTK notifications in worker methods"

requirements-completed: [SLACK-04, SLACK-05]

# Metrics
duration: 4min
completed: 2026-03-03
---

# Phase 8 Plan 04: Slack Integration Wiring Summary

**HuddleManager + SlackSocket wired into app.py with Block Kit post-huddle Slack publishing and dynamic Stop/Start Huddle Recording tray item**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-03T03:00:20Z
- **Completed:** 2026-03-03T03:04:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Wired HuddleManager, SlackManager, SlackSocket instantiation into app.py do_startup(); SlackSocket started per connected workspace
- All huddle callbacks implemented: auto-detect dispatch, auto-stop on huddle end (SLACK-05), Ctrl+Alt+H hotkey, tray toggle
- tray.py: Start/Stop Huddle Recording dynamic item with set_huddle_recording() toggle method
- HuddleManager.post_huddle_results(): Block Kit message + .md file upload with error notifications on failure

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire HuddleManager into app.py and tray.py** - `0b35193` (feat)
2. **Task 2: Implement post_huddle_results in HuddleManager** - `eb2ec05` (feat)

## Files Created/Modified
- `src/linux_speech_flow/app.py` - Imports SlackManager/HuddleManager/SlackSocket; do_startup wiring; all huddle callbacks (_on_huddle_event_detected, _on_huddle_end_detected, _on_huddle_start_for, _on_huddle_start, _on_huddle_stop, _on_huddle_toggle_tray, _on_huddle_session_complete, _on_huddle_dialog_submit, _on_huddle_analysis_complete)
- `src/linux_speech_flow/tray.py` - on_huddle_toggle param; _huddle_item in menu; set_huddle_recording() method
- `src/linux_speech_flow/huddle_manager.py` - post_huddle_results(); _build_huddle_result_blocks() @staticmethod

## Decisions Made
- `_on_huddle_dialog_submit` adapts the existing ConversationDialog `on_submit` contract (10 args) for huddle flow; simpler than introducing a new `on_complete` signature that doesn't match the actual dialog interface.
- `post_huddle_results` is post-only (does not save file); file save happens in `_on_huddle_dialog_submit` via `coalesce_file`, consistent with the plan's "local file always saved regardless" requirement.
- `_on_huddle_toggle_tray` uses `HuddleManager.is_active()` (already existed from plan 03) to avoid coupling tray to HotkeyManager internals.
- SlackSocket loop in do_startup() naturally handles no-workspace case: zero iterations, zero sockets.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ConversationDialog on_complete vs on_submit signature mismatch**
- **Found during:** Task 1 (_on_huddle_session_complete implementation)
- **Issue:** Plan showed `ConversationDialog(on_complete=lambda result, saved_path: ...)` but actual ConversationDialog.__init__ takes `on_submit` with a 10-arg signature (transcript, prompt, qualifying_answers, selected_models, save_to_file, inject_to_window, metadata, copy_to_clipboard, paste_to_window, window_info). No `on_complete` parameter exists.
- **Fix:** Implemented `_on_huddle_dialog_submit` that accepts the 10-arg `on_submit` contract and adds `huddle_metadata` kwarg via lambda closure; wired `on_finalised` to call `_on_huddle_analysis_complete`. This correctly re-uses the existing pipeline flow.
- **Files modified:** src/linux_speech_flow/app.py
- **Verification:** Import verification + 241 tests pass
- **Committed in:** 0b35193 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in plan interface spec)
**Impact on plan:** Fix was necessary for correctness; functional outcome matches plan intent exactly. No scope creep.

## Issues Encountered
None beyond the on_complete/on_submit interface mismatch (documented above).

## User Setup Required
None - no external service configuration required for this plan. Slack workspace credentials configured in previous plans.

## Next Phase Readiness
- All Phase 8 Slack integration components are now wired and functional
- SLACK-04 (hotkey + tray + auto-detect huddle recording) and SLACK-05 (post-huddle Slack publish) requirements satisfied
- 241 tests pass
- Phase 8 complete; ready for Phase 9 packaging

---
*Phase: 08-slack-integration*
*Completed: 2026-03-03*

## Self-Check: PASSED

- FOUND: src/linux_speech_flow/app.py
- FOUND: src/linux_speech_flow/tray.py
- FOUND: src/linux_speech_flow/huddle_manager.py
- FOUND: 0b35193 (Task 1 commit)
- FOUND: eb2ec05 (Task 2 commit)
- All 241 tests pass
