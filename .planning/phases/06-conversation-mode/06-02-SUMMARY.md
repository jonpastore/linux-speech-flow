---
phase: 06-conversation-mode
plan: 02
subsystem: audio
tags: [pasimple, pulseaudio, wav, threading, glib, silence-detection]

# Dependency graph
requires:
  - phase: 06-01
    provides: "Phase 6 scaffold — config keys, HotkeyManager _STATE_CONVERSATION, tray conv_recording state"
  - phase: 02-03
    provides: "recorder.py pasimple chunked recording pattern, RMS silence detection, MIN_SILENCE_GUARD_CHUNKS"
provides:
  - "ConversationRecorder class with start(), stop(), cleanup() API"
  - "Silence-bounded WAV chunk delivery via GLib.idle_add to GTK main thread"
  - "Thread-safe stop via threading.Event; temp dir cleanup via shutil.rmtree"
affects: [06-03, 06-04, 06-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Outer while loop drives multi-chunk capture; inner _record_one_chunk handles one silence-bounded segment"
    - "MIN_GUARD_FRAMES prevents false silence trigger on PulseAudio buffer fill latency at start"
    - "Pure-silence chunks (had_audio=False) silently discarded — on_chunk_ready not called"
    - "GLib.idle_add used for all GTK-thread callbacks from worker thread"

key-files:
  created:
    - src/linux_speech_flow/conversation_recorder.py
  modified: []

key-decisions:
  - "ConversationRecorder is a standalone class (not subclass of AudioRecorder) — AudioRecorder's single-file model is wrong for chunked long recording"
  - "chunk_silence_sec=3 default matches plan spec; configurable per-instance for future ConversationManager integration"
  - "had_audio flag distinguishes pure-silence chunks from speech chunks so leading-silence noise floor is discarded without firing on_chunk_ready"

patterns-established:
  - "Outer _record_loop calls _record_one_chunk in a loop — separation of multi-chunk session control from single-chunk WAV writing"
  - "GLib imported at module top level (not inside _record_loop) — import triggers GLib main loop connection before threading"

requirements-completed: [CONV-01]

# Metrics
duration: 1min
completed: 2026-02-21
---

# Phase 6 Plan 02: ConversationRecorder Summary

**Silence-bounded chunked WAV recorder delivering speech segments via GLib.idle_add for parallel Whisper transcription in Conversation Mode**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-21T18:09:21Z
- **Completed:** 2026-02-21T18:10:21Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Implemented ConversationRecorder as a standalone class entirely separate from AudioRecorder
- Silence-boundary detection using RMS with MIN_GUARD_FRAMES guard prevents false splits on PulseAudio buffer fill
- Each completed speech chunk written to disk and delivered via GLib.idle_add for parallel transcription

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement ConversationRecorder** - `541c181` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `src/linux_speech_flow/conversation_recorder.py` - ConversationRecorder class: chunked audio recorder with silence detection, start/stop/cleanup API, GLib.idle_add callback dispatch

## Decisions Made
- ConversationRecorder is a standalone class (not a subclass of AudioRecorder) — AudioRecorder's single-file model is architecturally wrong for the multi-chunk streaming use case required by Groq's 100MB file limit
- `chunk_silence_sec=3` default balances chunk granularity with natural speech pause patterns; configurable per-instance
- `had_audio` flag introduced to distinguish pure-silence chunks (noise floor, buffer fill at start) from actual speech segments — discards leading-silence without firing `on_chunk_ready`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- ConversationRecorder ready for integration in ConversationManager (06-03)
- `on_chunk_ready(wav_path)` callback delivers a closed, complete WAV file to the GTK main thread — consumer can immediately pass to Groq Whisper
- `cleanup()` must be called after all chunks consumed; consumer responsible for deleting individual chunk files after transcription

---
*Phase: 06-conversation-mode*
*Completed: 2026-02-21*
