---
phase: 02-audio-capture-and-hotkey
plan: "04"
subsystem: ui
tags: [pynput, gtk4, glib, hotkey, push-to-talk, state-machine, settings]

# Dependency graph
requires:
  - phase: 02-01
    provides: config keys (sounds_enabled, sounds_output_device, max_recording_duration, silence_stop_duration), list_sinks()
  - phase: 02-02
    provides: play_sound(), send_notification()
  - phase: 02-03
    provides: AudioRecorder with start()/stop()/on_complete/on_error callbacks
provides:
  - HotkeyManager with F9 push-to-talk state machine (IDLE/WAITING/RECORDING)
  - SettingsWindow Audio section with 4 Phase 2 config fields
affects: [02-05, 03-transcription, 04-tray-indicator]

# Tech tracking
tech-stack:
  added: [pynput keyboard.Listener]
  patterns: [GLib.idle_add for cross-thread GTK dispatch, GLib.timeout_add for debounce timer, 300ms debounce guard against brief F9 taps]

key-files:
  created:
    - src/linux_speech_flow/hotkey.py
  modified:
    - src/linux_speech_flow/settings.py

key-decisions:
  - "suppress=True NOT used on pynput Listener — would crash X11 sessions (pynput issue #269)"
  - "_on_recorder_complete plays stop.wav before calling on_complete_cb — auto-stop paths (silence timeout, max duration) play the descending chime per CONTEXT.md Area 2"
  - "mark_started() guard prevents F9 held at app startup from triggering recording"
  - "All pynput thread → GTK dispatches go via GLib.idle_add; timer via GLib.timeout_add"

patterns-established:
  - "pynput callbacks dispatch to GTK thread via GLib.idle_add, never call GTK directly"
  - "State machine prevents double-start: second F9 press in WAITING or RECORDING is a no-op"

requirements-completed: [CORE-01, CORE-02, CORE-04, CORE-05]

# Metrics
duration: 1min
completed: 2026-02-19
---

# Phase 2 Plan 04: HotkeyManager and Settings Audio Section Summary

**F9 push-to-talk state machine (IDLE/WAITING/RECORDING, 300ms debounce) wired to AudioRecorder/sounds/notifications, plus SettingsWindow Audio section with 4 config fields**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-19T13:40:58Z
- **Completed:** 2026-02-19T13:42:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- HotkeyManager with 3-state push-to-talk machine: brief F9 tap silently ignored, long hold starts recording with start.wav chime and notification
- ESC cancel path deletes WAV; F9 release and auto-stop paths play stop.wav and call on_complete_cb
- SettingsWindow Audio section with sounds toggle, sink picker (list_sinks()), max duration spin, silence auto-stop spin
- All 4 Phase 2 config keys (sounds_enabled, sounds_output_device, max_recording_duration, silence_stop_duration) saved by _on_save

## Task Commits

Each task was committed atomically:

1. **Task 1: HotkeyManager — pynput Listener with push-to-talk state machine** - `83cba6b` (feat)
2. **Task 2: Settings Audio section — 4 new fields for Phase 2 config** - `12ccb5f` (feat)

## Files Created/Modified
- `src/linux_speech_flow/hotkey.py` - HotkeyManager: F9 hold-to-record state machine, 300ms debounce, GLib.idle_add threading, play_sound/send_notification wiring
- `src/linux_speech_flow/settings.py` - Audio section added: sounds toggle, sink ComboBoxText, max duration SpinButton, silence SpinButton; _on_save writes all 4 config keys

## Decisions Made
- suppress=True NOT used on pynput Listener (X11 crash, pynput #269)
- _on_recorder_complete plays stop.wav before on_complete_cb so auto-stop paths produce the descending chime
- mark_started() called via GLib.idle_add after first GTK tick to guard against F9 held at startup

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- HotkeyManager ready for wiring into Application.do_startup() in Phase 2 Plan 05
- SettingsWindow Audio section complete; config keys saved correctly
- All 22 existing tests continue to pass

---
*Phase: 02-audio-capture-and-hotkey*
*Completed: 2026-02-19*
