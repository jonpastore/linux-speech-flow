---
phase: 03-transcription-and-text-injection
plan: "05"
subsystem: ui
tags: [gtk4, gtk-window, modal, reprocess, batch, transcription]

requires:
  - phase: 03-04
    provides: TranscriptionPipeline with submit(), FAILED_DIR, F10 hotkey wiring in app.py

provides:
  - ReprocessDialog GTK4 modal window (reprocess_dialog.py) with checkbox list and mode selection
  - _ModeSelectWindow for batch reprocess mode (paste vs file)
  - TranscriptionPipeline.submit_batch_to_file() for batch WAV-to-file transcription
  - batch_output_path handling in TranscriptionPipeline._process() to write transcripts to file

affects:
  - 03-06
  - app.py (already wired in 03-04, lazy import resolves now that module exists)

tech-stack:
  added: []
  patterns:
    - "Gtk.Window with set_modal(True) for modal dialogs (Gtk.Dialog deprecated in GTK 4.10)"
    - "batch_output_path key in window_info dict overrides normal paste behavior to file append"
    - "xdg-open subprocess.Popen fires when _queue.empty() after last batch item"

key-files:
  created:
    - src/linux_speech_flow/reprocess_dialog.py
  modified:
    - src/linux_speech_flow/transcription.py

key-decisions:
  - "Gtk.Window + set_modal(True) instead of Gtk.Dialog — Gtk.Dialog deprecated since GTK 4.10"
  - "batch_output_path field injected into window_info dict — zero-overhead signal, no new queue type needed"
  - "xdg-open fires on queue empty heuristic after last batch item — pragmatic, works for serial FIFO processing"
  - "tempfile.mktemp() for batch output path — file pre-created (open/close) to ensure it exists before workers write"

patterns-established:
  - "Modal child windows: Gtk.Window(modal=True) + set_transient_for(parent)"
  - "Callback-based dialog result: on_selected(wav_paths, mode) decouples dialog from app logic"

requirements-completed: [TRANS-07, TRANS-08, TRANS-09]

duration: 2min
completed: 2026-02-20
---

# Phase 3 Plan 05: Reprocess Dialog and Batch-to-File Summary

**GTK4 ReprocessDialog modal window with checkbox list and mode selection, plus TranscriptionPipeline.submit_batch_to_file() writing batch transcripts to xdg-open'd temp file**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-20T04:07:28Z
- **Completed:** 2026-02-20T04:09:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created reprocess_dialog.py with ReprocessDialog (Gtk.Window, modal) listing failed WAVs as pre-checked checkboxes
- _ModeSelectWindow inner modal for choosing "Paste each" vs "Write all to file" on Reprocess All
- Added submit_batch_to_file() to TranscriptionPipeline queuing WAVs with batch_output_path override
- _process() batch_output_path branch appends transcripts to temp file, opens via xdg-open when queue drains

## Task Commits

Each task was committed atomically:

1. **Task 1: ReprocessDialog GTK4 modal window** - `c061204` (feat)
2. **Task 2: Add submit_batch_to_file() to TranscriptionPipeline** - `183af8e` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/linux_speech_flow/reprocess_dialog.py` - ReprocessDialog and _ModeSelectWindow GTK4 classes
- `src/linux_speech_flow/transcription.py` - submit_batch_to_file() method + batch_output_path handling in _process()

## Decisions Made

- Gtk.Window + set_modal(True) over Gtk.Dialog — Gtk.Dialog is deprecated since GTK 4.10; consistent with existing codebase approach
- batch_output_path key in window_info dict — lightweight signal that requires no new queue type or thread coordination
- xdg-open fires on queue empty heuristic — pragmatic for serial FIFO processing; rare race condition acceptable
- tempfile.mktemp() with pre-creation (open/close) — ensures file exists for concurrent worker appends

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. GTK display test required DISPLAY=:1 (not :0), discovered via xdpyinfo — auto-detected.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ReprocessDialog is fully wired: app.py already imports via lazy import in _on_reprocess_hotkey (per 03-04 decision)
- Full F10 flow is end-to-end: F10 -> _on_reprocess_hotkey -> ReprocessDialog -> on_selected -> pipeline.submit() or submit_batch_to_file()
- Plan 06 can proceed (final phase of Phase 3)

## Self-Check: PASSED

- FOUND: src/linux_speech_flow/reprocess_dialog.py
- FOUND: src/linux_speech_flow/transcription.py (modified)
- FOUND: .planning/phases/03-transcription-and-text-injection/03-05-SUMMARY.md
- FOUND commit: c061204 (Task 1 - ReprocessDialog)
- FOUND commit: 183af8e (Task 2 - submit_batch_to_file)
- All 22 existing tests pass

---
*Phase: 03-transcription-and-text-injection*
*Completed: 2026-02-20*
