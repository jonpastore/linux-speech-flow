---
phase: 02-audio-capture-and-hotkey
plan: "03"
subsystem: audio
tags: [pasimple, pulseaudio, threading, wav, rms-silence-detection]

requires:
  - phase: 02-audio-capture-and-hotkey
    provides: pyproject.toml with pasimple>=0.0.3 dependency declared (plan 01)

provides:
  - AudioRecorder class — pasimple recording thread with RMS silence detection
  - 16kHz mono s16le WAV written to /tmp via daemon thread
  - on_complete/on_error callbacks dispatched via GLib.idle_add to GTK main thread

affects:
  - 02-04 (hotkey handler will call AudioRecorder.start/stop)
  - 02-05 (settings window changes for max_recording_duration, silence_stop_duration)
  - 03 (transcription phase receives WAV path from on_complete callback)

tech-stack:
  added: [pasimple (already in pyproject.toml from plan 01)]
  patterns:
    - daemon thread for audio capture so GTK main loop never blocks
    - GLib.idle_add for cross-thread GTK callback dispatch
    - threading.Event for cooperative stop signaling
    - tempfile.NamedTemporaryFile for WAV lifecycle in /tmp

key-files:
  created:
    - src/linux_speech_flow/recorder.py
  modified: []

key-decisions:
  - "device_name uses 'or None' to coerce empty string to None for PulseAudio default source"
  - "PaSimpleError caught around entire pasimple context block (covers stream open + mid-read disconnects)"
  - "MIN_SILENCE_GUARD_CHUNKS=10 (1 second) prevents false silence trigger on PulseAudio buffer fill latency"
  - "GLib deferred import inside daemon thread avoids import-time GTK requirement while keeping thread-safety"
  - "WAV written incrementally per chunk (not buffered in memory) to support long recordings"

patterns-established:
  - "Daemon thread pattern: start() spawns thread, stop() sets Event, thread checks is_set() per chunk"
  - "Callback dispatch: GLib.idle_add(callback, arg) routes from daemon thread to GTK main thread"
  - "Silence guard: MIN_SILENCE_GUARD_CHUNKS chunks must pass before RMS detection activates"

requirements-completed: [CORE-02, CORE-03]

duration: 2min
completed: 2026-02-19
---

# Phase 2 Plan 03: AudioRecorder Summary

**pasimple-backed daemon thread records 16kHz mono s16le WAV to /tmp with RMS silence detection and GLib.idle_add callback dispatch**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T13:34:31Z
- **Completed:** 2026-02-19T13:36:31Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- AudioRecorder class implementing the full core audio engine for the application
- pasimple PaSimple context manager in daemon thread captures PA_STREAM_RECORD audio
- Per-chunk RMS silence detection with 1-second guard to prevent false triggers on buffer fill
- Max duration auto-stop and silence auto-stop both produce WAV and call on_complete normally
- PaSimpleError caught around entire pasimple context (stream open failures + mid-record disconnects)
- Cancel path deletes temp WAV and skips on_complete callback

## Task Commits

Each task was committed atomically:

1. **Task 1: AudioRecorder class with pasimple recording thread** - `45e5f3f` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/linux_speech_flow/recorder.py` - AudioRecorder class with pasimple daemon thread, RMS silence detection, WAV lifecycle management

## Decisions Made

- Used `device_name or None` in `__init__` to coerce empty string config values to None, since PulseAudio requires None (not `""`) for default source selection
- PaSimpleError wraps the entire `with pasimple.PaSimple(...) as pa:` block because the error fires at `__enter__` for device-not-found, not just at `read()`
- MIN_SILENCE_GUARD_CHUNKS=10 (1 second) prevents false silence trigger during PulseAudio buffer fill latency at recording start
- GLib imported inside daemon thread (deferred) to avoid import-time GTK requirement while maintaining thread-safety via idle_add reentrancy

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- AudioRecorder is complete and ready for Plan 04 (hotkey handler) to call start()/stop()
- on_complete callback will deliver WAV path to Plan 03 of Phase 3 (transcription)
- silence_stop_duration and max_duration parameters are wired for Plan 05 settings window additions

---
*Phase: 02-audio-capture-and-hotkey*
*Completed: 2026-02-19*
