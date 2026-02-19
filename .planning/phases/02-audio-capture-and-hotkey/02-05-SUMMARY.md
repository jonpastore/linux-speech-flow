---
phase: 02-audio-capture-and-hotkey
plan: "05"
subsystem: ui
tags: [gtk, pynput, hotkey, audio, pyaudio, pasimple, settings]

# Dependency graph
requires:
  - phase: 02-04
    provides: HotkeyManager push-to-talk state machine and AudioRecorder
  - phase: 01-04
    provides: Gtk.Application App class with do_activate and settings wiring
provides:
  - HotkeyManager wired into App.do_startup() with full GTK lifecycle (startup/shutdown)
  - Complete Phase 2 flow: F9 toggle-to-record with start/stop chimes, notifications, WAV output
  - Human-verified end-to-end: tap ignored, normal stop, escape cancel, silence auto-stop, settings persist
affects: [03-transcription, all future phases using App class]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GLib.idle_add(mark_started) guard defers startup protection to first GTK main loop tick"
    - "do_startup/do_shutdown use Gtk.Application.do_startup(self) (not super()) for PyGObject compat"
    - "Toggle mode: F9 starts recording, ESC stops — not hold-to-record as originally planned"
    - "WAV temp file cleanup in _on_recording_complete after Phase 2 stub (Phase 3 will consume WAV before cleanup)"

key-files:
  created: []
  modified:
    - src/linux_speech_flow/app.py
    - src/linux_speech_flow/hotkey.py
    - src/linux_speech_flow/settings.py

key-decisions:
  - "Toggle mode (F9 start, ESC stop) chosen over hold-to-record — discovered hold mode impractical for longer dictation sessions"
  - "do_startup/do_shutdown call Gtk.Application.do_startup(self) explicitly — super() segfaults under PyGObject on Python 3.10"
  - "Stop chime played only in _on_recorder_complete, not _stop_recording — prevents double chime on all stop paths"
  - "WAV cleanup in _on_recording_complete Phase 2 stub — Phase 3 must consume WAV before the callback returns"
  - "Mic moved into Audio section of settings (not Microphone section) for logical grouping with audio controls"
  - "Max duration spinner uses 10-second steps with scroll blocked to prevent accidental value changes"

patterns-established:
  - "GLib.idle_add for post-startup guards: mark_started() pattern protects against key-held-at-startup"
  - "Phase stub callbacks (_on_recording_complete, _on_recording_error) print to terminal in Phase 2; Phase 3 replaces with transcription"

requirements-completed: [CORE-01, CORE-02, CORE-03, CORE-04, CORE-05]

# Metrics
duration: 15min
completed: 2026-02-19
---

# Phase 2 Plan 05: App Wiring & Human Verification Summary

**F9 toggle-to-record wired end-to-end: pynput hotkey -> pasimple recording -> WAV output, with chime feedback, ESC cancel, silence auto-stop, and human-verified in running GTK app**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-02-19T13:30:00Z
- **Completed:** 2026-02-19T13:45:00Z
- **Tasks:** 2 (1 auto + 1 human-verify)
- **Files modified:** 3

## Accomplishments

- HotkeyManager integrated into App.do_startup() with GLib.idle_add mark_started guard
- do_shutdown() cleanly stops the pynput listener on app exit
- Human verified all 5 primary scenarios: tap ignored, normal stop, escape cancel, settings persist, silence auto-stop

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire HotkeyManager into App.do_startup()** - `f5bcee5` (feat)
2. **Task 2: Human verification** - approved by user (no code commit)

## Files Created/Modified

- `src/linux_speech_flow/app.py` - Added HotkeyManager wiring: do_startup(), do_shutdown(), _on_recording_complete(), _on_recording_error()
- `src/linux_speech_flow/hotkey.py` - Toggle mode, double-stop chime fix, cancel on shutdown
- `src/linux_speech_flow/settings.py` - Mic moved to Audio section; spinner step/scroll adjustments

## Decisions Made

- Toggle mode (F9 start, ESC stop) over hold-to-record: hold-to-record is impractical for longer dictation
- PyGObject compat: use `Gtk.Application.do_startup(self)` not `super()` — `super()` segfaults on Python 3.10 with PyGObject
- Single stop chime location: only in `_on_recorder_complete`, not in `_stop_recording`, prevents double chime on all stop paths including ESC cancel

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Changed hold-to-record to toggle mode (F9 start, ESC stop)**
- **Found during:** Task 1 (integration wiring) and human verification
- **Issue:** Hold-to-record model is impractical for real dictation — user must hold F9 for the full duration of speech. Toggle mode (press F9 to start, press ESC to stop) is far more usable.
- **Fix:** Refactored hotkey.py pynput callbacks from on_press/on_release hold detection to toggle: F9 on_press starts recording, ESC on_press stops.
- **Files modified:** src/linux_speech_flow/hotkey.py
- **Verification:** Human verified F9 starts, ESC stops correctly
- **Committed in:** f5bcee5

**2. [Rule 1 - Bug] Fixed double stop chime**
- **Found during:** Human verification
- **Issue:** Stop chime was playing twice — once in _stop_recording() and once in _on_recorder_complete(). All stop paths call _on_recorder_complete, so _stop_recording should not also play the chime.
- **Fix:** Removed play_sound('stop') from _stop_recording(); kept it only in _on_recorder_complete().
- **Files modified:** src/linux_speech_flow/hotkey.py
- **Verification:** Human confirmed single chime on all stop paths
- **Committed in:** f5bcee5

**3. [Rule 1 - Bug] Fixed PyGObject super() segfault in do_startup/do_shutdown**
- **Found during:** Task 1 testing
- **Issue:** Using `super().do_startup()` segfaults in PyGObject on Python 3.10 when overriding GTK vfuncs. Must call `Gtk.Application.do_startup(self)` explicitly.
- **Fix:** Replaced `super().do_startup()` / `super().do_shutdown()` with direct class calls.
- **Files modified:** src/linux_speech_flow/app.py
- **Verification:** App starts cleanly without segfault; 22 tests pass
- **Committed in:** f5bcee5

**4. [Rule 2 - Missing Critical] Added WAV temp file cleanup in _on_recording_complete**
- **Found during:** Task 1 (Phase 2 stub callback review)
- **Issue:** WAV files written to /tmp were never deleted; would accumulate indefinitely.
- **Fix:** Added os.unlink(wav_path) after logging the path in the Phase 2 stub callback. Phase 3 must consume the WAV before calling super/cleanup.
- **Files modified:** src/linux_speech_flow/app.py
- **Verification:** /tmp WAV files removed after each recording in human test
- **Committed in:** f5bcee5

**5. [Rule 2 - Missing Critical] Cancel recording on app shutdown**
- **Found during:** Task 1 (do_shutdown review)
- **Issue:** If app is quit during an active recording, the AudioRecorder thread would be orphaned.
- **Fix:** HotkeyManager.stop() calls _stop_recording() if recording is active before stopping the pynput listener.
- **Files modified:** src/linux_speech_flow/hotkey.py
- **Verification:** App quits cleanly even when recording is in progress
- **Committed in:** f5bcee5

**6. [Rule 1 - Bug] Settings: moved mic into Audio section, fixed spinner behavior**
- **Found during:** Human verification of Settings scenario
- **Issue:** Microphone field was in a separate section rather than grouped with Audio controls; duration spinner scroll-wheel was too sensitive.
- **Fix:** Moved mic dropdown into Audio section in settings.py; set max_duration_spin step to 10 seconds; blocked scroll-wheel on both spinners.
- **Files modified:** src/linux_speech_flow/settings.py
- **Verification:** Human confirmed settings layout and save/reload
- **Committed in:** f5bcee5

---

**Total deviations:** 6 auto-fixed (3 bugs, 2 missing critical, 1 bug/UX)
**Impact on plan:** All auto-fixes necessary for correct operation, usability, or resource hygiene. Toggle mode is a meaningful UX improvement over hold-to-record. No scope creep.

## Issues Encountered

- PyGObject `super()` calling convention for overriding GTK vfuncs is a known footgun on Python 3.10 — must use explicit class method calls.
- pynput hold-to-record model discovered to be impractical during live test; toggle mode adopted.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 complete: F9 toggle recording -> WAV file -> stub callback ready for Phase 3
- Phase 3 entry point: replace `_on_recording_complete(wav_path)` in app.py with Groq Whisper transcription call
- All 22 tests pass; HotkeyManager, AudioRecorder, sounds, notify all verified
- Blocker to track: validate pasimple is actively maintained before committing to Phase 3 integration

---
*Phase: 02-audio-capture-and-hotkey*
*Completed: 2026-02-19*
