---
phase: 03-transcription-and-text-injection
plan: "02"
subsystem: transcription
tags: [groq, whisper, llm, xclip, xdotool, queue, threading, glib, wayland, x11]

requires:
  - phase: 03-01
    provides: config defaults (whisper_model, llm_model, app_categories, llm_system_prompt), groq in pyproject.toml, processing.wav, success.wav
  - phase: 02-02
    provides: play_sound(), send_notification(), sounds/__init__.py pattern
  - phase: 02-03
    provides: recorder.py daemon thread + GLib.idle_add pattern this pipeline mirrors

provides:
  - TranscriptionPipeline class with daemon worker thread and queue.Queue
  - get_active_window_info() for X11 window capture before API calls
  - paste_text() for xclip+xdotool injection with Wayland fallback
  - _call_with_retry() Fibonacci backoff utility (5s,8s,13s,21s,34s)
  - WAV lifecycle management: success=unlink, failure=move to failed/
  - Silence detection via MIN_TRANSCRIPT_LEN=3 guard
  - LLM fallback to raw Whisper transcript on post-processing failure

affects: [03-04, 03-05, 03-06]

tech-stack:
  added: [groq>=1.0.0 (Whisper + LLM), xclip (system), xdotool (system), xprop (system)]
  patterns:
    - Daemon worker thread consuming queue.Queue, GTK side-effects via GLib.idle_add (mirrors recorder.py)
    - max_retries=0 on Groq client — Fibonacci wrapper is sole retry mechanism
    - Window context captured at submit() time (GTK thread) not in worker thread (avoids focus-theft)
    - WAV lifecycle owned entirely by pipeline worker: unlink on success, shutil.move on failure

key-files:
  created:
    - src/linux_speech_flow/transcription.py
    - src/linux_speech_flow/window_context.py
    - src/linux_speech_flow/injector.py
  modified: []

key-decisions:
  - "groq client max_retries=0: Fibonacci retry wrapper is sole mechanism; SDK default 2x retries would create 10 total attempts with unpredictable backoff interaction"
  - "Window context captured at submit() on GTK main thread, not in worker: prevents focus-theft from processing notification stealing window ID during API calls"
  - "Wayland paste: wl-copy for clipboard write, skip keystroke injection (ydotoold daemon not required); notify user to paste manually"
  - "LLM failure falls back to raw Whisper transcript (TRANS-05) rather than failing entirely"
  - "Ctrl+Shift+V for terminals, Ctrl+V for all other app categories including code editors"
  - "MIN_TRANSCRIPT_LEN=3: catches empty string, single chars, and common Whisper artifacts like . or Hmm."

patterns-established:
  - "Pattern: Worker thread always dispatches GTK side-effects (play_sound, send_notification, paste_text) via GLib.idle_add"
  - "Pattern: Fibonacci retry applied independently per API call — Whisper and LLM each have 5-attempt budgets"
  - "Pattern: _build_user_message() constructs XML-style context and vocabulary blocks for LLM prompt injection"

requirements-completed: [TRANS-01, TRANS-02, TRANS-03, TRANS-04, TRANS-05, TRANS-06, TRANS-08]

duration: 3min
completed: 2026-02-20
---

# Phase 3 Plan 02: Transcription Pipeline Summary

**TranscriptionPipeline class with Groq Whisper + LLM post-processing, Fibonacci retry, xclip+xdotool injection, and WAV lifecycle management**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-20T03:53:58Z
- **Completed:** 2026-02-20T03:56:55Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Three core pipeline modules implemented: transcription.py (230 lines), window_context.py (56 lines), injector.py (57 lines)
- TranscriptionPipeline starts daemon worker thread, processes WAVs FIFO via queue.Queue, dispatches all GTK side-effects via GLib.idle_add
- Groq Whisper + LLM calls with Fibonacci retry (5s/8s/13s/21s/34s per API call independently), LLM fallback to raw transcript on failure
- xclip+xdotool injection with window ID captured pre-API to prevent focus-theft; Wayland fallback via wl-copy

## Task Commits

Each task was committed atomically:

1. **Task 1: window_context.py and injector.py** - `e6a148b` (feat)
2. **Task 2: transcription.py with Fibonacci retry, failed WAV storage, GLib dispatch** - `ca57500` (feat)

## Files Created/Modified

- `src/linux_speech_flow/transcription.py` - TranscriptionPipeline: queue, worker thread, Whisper/LLM calls, retry, WAV lifecycle
- `src/linux_speech_flow/window_context.py` - get_active_window_info() for X11 window detection and app category classification
- `src/linux_speech_flow/injector.py` - paste_text() for xclip clipboard write + xdotool keystroke injection

## Decisions Made

- `groq.Groq(max_retries=0)` to prevent SDK retries conflicting with Fibonacci wrapper (10x total attempts otherwise)
- Window context captured at `submit()` on GTK main thread before queuing — xdotool at paste time would send to wrong window if a notification stole focus during API calls
- Wayland: write to wl-copy clipboard, skip keystroke (ydotoold daemon not required), notify user to press Ctrl+V
- LLM failure is non-fatal: raw Whisper transcript pasted as fallback with subtle notification
- `_call_with_retry` retry loop: first attempt fires without sleeping; sleeps happen between attempts — 5 total attempts using each Fibonacci delay once

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- groq not yet installed in venv (Plan 01 added it to pyproject.toml but did not pip install). Installed via `pip install "groq>=1.0.0"` per plan instructions. Pre-existing tokenizers/huggingface-hub version conflict warning present but unrelated.

## User Setup Required

None - GROQ_API_KEY was configured during Phase 1 wizard setup (stored in ~/.config/linux-speech-flow/config.json).

## Next Phase Readiness

- All three pipeline modules import cleanly; 22 existing tests pass unchanged
- TranscriptionPipeline is ready to be wired into app.py (Plan 04) via `self._pipeline = TranscriptionPipeline(...)`
- Plan 03 (app.py wiring) or Plan 04 must replace the Phase 2 stub in `_on_recording_complete` that deletes the WAV — pipeline now owns WAV lifecycle

---
*Phase: 03-transcription-and-text-injection*
*Completed: 2026-02-20*
