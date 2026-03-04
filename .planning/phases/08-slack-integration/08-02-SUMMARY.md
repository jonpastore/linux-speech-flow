---
phase: 08-slack-integration
plan: 02
subsystem: ui
tags: [pulseaudio, pulsectl, pactl, gtk, null-sink, loopback, huddle, recording]

requires:
  - phase: 08-01
    provides: SlackManager, huddle hotkey in HotkeyManager, Settings Integrations section
  - phase: 06-conversation-mode
    provides: ConversationRecorder (chunked audio recorder with silence detection)

provides:
  - huddle_recorder.py: HuddleRecorder class — null-sink PulseAudio setup/teardown, crash recovery, ConversationRecorder composition
  - huddle_status.py: HuddleStatusWindow GTK class — elapsed timer, chunk count, transcript, confidence, last command, recording mode badge, Slack status dot
  - tests/test_huddle_recorder.py: 27 tests covering null-sink setup/teardown, crash recovery, finally-block guarantee

affects: [08-03, 08-04, 08-05]

tech-stack:
  added: []
  patterns:
    - "HuddleRecorder uses ConversationRecorder composition (not inheritance) pointed at lsf-huddle-mix.monitor"
    - "PulseAudio null-sink setup via pactl subprocess; module IDs tracked in list for reverse-order teardown"
    - "_existing_sink_module_id() pulsectl check before start for crash recovery — unloads stale module if found"
    - "Teardown in finally block of start() ensures cleanup even when ConversationRecorder.start() raises"

key-files:
  created:
    - src/linux_speech_flow/huddle_recorder.py
    - src/linux_speech_flow/huddle_status.py
    - tests/test_huddle_recorder.py
  modified: []

key-decisions:
  - "HuddleRecorder uses ConversationRecorder composition (not inheritance) — separate architecture matches ConversationRecorder's existing standalone design"
  - "HuddleStatusWindow is a separate class from ConversationStatusWindow — no silence timer (not meaningful for huddle, locked CONTEXT.md decision)"
  - "Crash recovery uses pulsectl to check for existing lsf-huddle-mix sink; unloads by owner_module ID"
  - "Teardown is in a try/except block in start() (not finally) so that module_ids are cleared and re-raise happens correctly"

patterns-established:
  - "PulseAudio module ID list: pactl stdout stripped to get numeric module ID; reversed list on teardown"
  - "HuddleStatusWindow update API: all update_* methods operate on GTK main thread; no background thread access"

requirements-completed: [SLACK-02, SLACK-03]

duration: 10min
completed: 2026-03-04
---

# Phase 8 Plan 02: HuddleRecorder and HuddleStatusWindow Summary

**Dual-source PulseAudio null-sink recording (mic + system audio) via HuddleRecorder, and dedicated GTK status window HuddleStatusWindow without silence timer**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-04T03:47:48Z
- **Completed:** 2026-03-04T03:57:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- HuddleRecorder class: creates PulseAudio null-sink (lsf-huddle-mix) mixing mic + system monitor via two loopback modules; wraps ConversationRecorder for chunked recording
- Crash recovery: detects existing lsf-huddle-mix sink at start() via pulsectl and unloads it before recreating
- Teardown guarantee: module_ids unloaded if ConversationRecorder.start() raises, and always on stop()
- HuddleStatusWindow: GTK4 status display with 9 elements (elapsed, chunks, transcript, confidence/color, last command, command spinner, recording badge, Slack dot, workspace label); no silence timer
- 27 tests covering all HuddleRecorder paths with full mock isolation (subprocess.run + pulsectl.Pulse)

## Task Commits

1. **Task 1: HuddleRecorder (null-sink composition) + tests** - `398ecef` (feat) - test + implementation
2. **Task 2: HuddleStatusWindow GTK class** - committed in prior session `806d73e` (feat, as 08-03 prereq)

## Files Created/Modified

- `src/linux_speech_flow/huddle_recorder.py` - HuddleRecorder: null-sink setup, crash recovery, ConversationRecorder composition, teardown in finally
- `src/linux_speech_flow/huddle_status.py` - HuddleStatusWindow: 9 display elements, update API, no silence timer
- `tests/test_huddle_recorder.py` - 27 tests: setup/teardown sequence, crash recovery, finally-block guarantee, module ID stripping

## Decisions Made

- HuddleRecorder uses ConversationRecorder by composition (not inheritance) — consistent with ConversationRecorder's standalone design
- HuddleStatusWindow is completely separate from ConversationStatusWindow — shares no code, uses no silence timer (locked CONTEXT.md decision)
- pulsectl used for sink existence check; pactl subprocess used for module operations — consistent with research patterns in 08-RESEARCH.md
- Teardown modules in reversed order (loopback 2, loopback 1, null-sink) to remove dependents before the sink they feed into

## Deviations from Plan

### Implementation Already Present

Both `huddle_recorder.py` and `huddle_status.py` were already created in a prior session (commit `806d73e`: "implement SlackSocket, HuddleRecorder, HuddleStatusWindow (08-02 prereqs)") as prerequisites for 08-03. The files match the plan specification exactly.

The test file (`tests/test_huddle_recorder.py`) was new and added in this execution session (commit `398ecef`).

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mock StopIteration for teardown calls**
- **Found during:** Task 1 (TDD test writing)
- **Issue:** `test_start_teardown_on_recorder_start_exception` set `mock_run.side_effect` to a 3-item list (load results) but teardown also calls subprocess.run 3 more times — StopIteration after 3 calls
- **Fix:** Added 3 additional `MagicMock()` teardown results to the side_effect list
- **Files modified:** tests/test_huddle_recorder.py
- **Verification:** All 27 tests pass
- **Committed in:** `398ecef` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test mock setup)
**Impact on plan:** Minor test infrastructure fix. No scope creep. Implementation was pre-existing and correct.

## Issues Encountered

- Both source files were already implemented in a prior session as prerequisites for 08-03. Tests were the only new work in this session. This is correct — the implementation matches the plan spec exactly.
- Plan verification check `assert 'silence' not in src.lower()` is too strict — the docstring says "NOT included: silence timer" which contains the word "silence". Verified functionally: no `update_silence`, `silence_frames`, or `silence_timer` in HuddleStatusWindow.

## Next Phase Readiness

- HuddleRecorder fully tested (27 tests) — ready for HuddleManager integration in 08-03
- HuddleStatusWindow complete with full update API — ready for HuddleManager to drive its display
- 241 tests pass total

## Self-Check: PASSED

- FOUND: src/linux_speech_flow/huddle_recorder.py
- FOUND: src/linux_speech_flow/huddle_status.py
- FOUND: tests/test_huddle_recorder.py
- FOUND: commit 398ecef (Task 1: HuddleRecorder + tests)
- FOUND: commit 806d73e (HuddleStatusWindow - prior session)
- All 241 tests pass

---
*Phase: 08-slack-integration*
*Completed: 2026-03-04*
