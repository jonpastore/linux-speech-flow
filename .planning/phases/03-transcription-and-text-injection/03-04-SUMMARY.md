---
phase: 03-transcription-and-text-injection
plan: "04"
subsystem: ui
tags: [gtkapplication, transcription-pipeline, hotkey, f10, reprocess]

requires:
  - phase: 03-02
    provides: TranscriptionPipeline with submit(), FAILED_DIR, on_paste_complete/on_error callbacks
  - phase: 02-05
    provides: HotkeyManager, App._on_recording_complete stub, WAV lifecycle

provides:
  - App._on_recording_complete submits WAV to TranscriptionPipeline instead of deleting it
  - F9 queue-depth notification when pipeline is busy (depth > 1)
  - F10 hotkey dispatches to App._on_reprocess_hotkey via HotkeyManager
  - _on_reprocess_hotkey handles 1-vs-many failed WAV logic (Plan 05 hooks in here)
  - HotkeyManager on_reprocess callback parameter and _on_f10 dispatch method

affects:
  - 03-05-reprocess-dialog
  - 04-tray-icon

tech-stack:
  added: []
  patterns:
    - "Lazy import of reprocess_dialog inside method body to avoid circular/missing-module errors at startup"
    - "TranscriptionPipeline created in do_startup() after HotkeyManager — both initialized before first GTK tick"

key-files:
  created: []
  modified:
    - src/linux_speech_flow/app.py
    - src/linux_speech_flow/hotkey.py

key-decisions:
  - "Lazy import of reprocess_dialog.py inside _on_reprocess_hotkey — module doesn't exist until Plan 05; deferred import prevents ImportError at startup"
  - "_on_recording_error in App now a no-op pass — HotkeyManager already shows mic-error notification; double notification avoided"

patterns-established:
  - "Method-level lazy import pattern for Plan 05 integration hooks"

requirements-completed: [TRANS-11, TRANS-07]

duration: 2min
completed: 2026-02-20
---

# Phase 03 Plan 04: Wire TranscriptionPipeline and F10 Hotkey Summary

**TranscriptionPipeline wired into App._on_recording_complete with F10 reprocess dispatch and queue-depth notification replacing the Phase 2 WAV-delete stub**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-20T04:01:47Z
- **Completed:** 2026-02-20T04:03:47Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Replaced Phase 2 `_on_recording_complete` stub (which deleted the WAV) with `self._pipeline.submit(wav_path)` — pipeline now owns WAV lifecycle
- Queue-depth notification fires when `depth > 1` so user knows recordings are queued while pipeline is busy
- F10 hotkey wired end-to-end: pynput `_on_press` -> `GLib.idle_add(_on_f10)` -> `on_reprocess` callback -> `App._on_reprocess_hotkey`
- `_on_reprocess_hotkey` handles 1-WAV vs many-WAV branching; Plan 05 `ReprocessDialog` will be called for the multi-WAV case
- `TranscriptionPipeline` instantiated in `do_startup()` with paste-complete and error callbacks

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire TranscriptionPipeline into App and add F10 hotkey to HotkeyManager** - `5fe342c` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/linux_speech_flow/app.py` - Added TranscriptionPipeline import/init, replaced WAV-delete stub, added _on_reprocess_hotkey/_on_reprocess_selected/_on_paste_complete/_on_pipeline_error, updated HotkeyManager call with on_reprocess param
- `src/linux_speech_flow/hotkey.py` - Added on_reprocess parameter to __init__, F10 key handling in _on_press, new _on_f10() method

## Decisions Made

- Lazy import of `reprocess_dialog.py` inside `_on_reprocess_hotkey` body — the module doesn't exist until Plan 05. Deferred import avoids `ImportError` at startup while keeping the integration hook in place.
- `_on_recording_error` in `App` is now a no-op `pass` — `HotkeyManager._on_recorder_error` already sends the microphone notification; propagating it to App would cause double notification.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- F10 dispatch wired; `_on_reprocess_hotkey` is ready for Plan 05 to implement `ReprocessDialog`
- `_on_reprocess_selected` with `paste` and `file` modes is implemented; Plan 05 needs to add `submit_batch_to_file` to `TranscriptionPipeline`
- All 22 existing tests pass

---
*Phase: 03-transcription-and-text-injection*
*Completed: 2026-02-20*
