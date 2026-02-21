---
phase: 06-conversation-mode
plan: "06"
subsystem: ui
tags: [gtk4, conversation-mode, qa-window, dialog, threading, audio-recorder]

requires:
  - phase: 06-03
    provides: ConversationPipeline with analyze(), continue_qa(), coalesce_file(), conv_filename()
  - phase: 06-04
    provides: ConversationManager session lifecycle and transcript assembly
  - phase: 06-02
    provides: ConversationRecorder chunk-based recording pattern

provides:
  - ConversationDialog: post-stop analysis configuration window (qualifying questions, prompt, model selection, save/inject)
  - ConversationQAWindow: iterative AI Q&A chat interface with Speak button, confidence tracking, and finalisation

affects: [06-07, 06-08, app-py-integration]

tech-stack:
  added: []
  patterns:
    - "Gtk.ApplicationWindow for all modal dialogs (never Gtk.Dialog — deprecated since GTK 4.10)"
    - "threading.Thread(daemon=True) for pipeline calls + GLib.idle_add for UI result dispatch"
    - "AudioRecorder inline in QA window for Speak button (same pattern as main app)"
    - "User must confirm before _finalise() runs (both AI confidence and user confirmation required)"

key-files:
  created:
    - src/linux_speech_flow/conversation_dialog.py
    - src/linux_speech_flow/conversation_qa.py
  modified: []

key-decisions:
  - "ConversationDialog _on_submit fallback: always at least groq in selected_models even if no checkbox is active"
  - "Speak button fills answer entry for user review before submit (not auto-submit) — consistent with CONTEXT.md Claude's Discretion"
  - "Confidence >= 0.95 shows confirmation dialog; _finalise() is never called without explicit user [Finalise] click"
  - "Done button always shows warning dialog — confidence <95% shows incomplete warning, >=95% shows normal confirmation"
  - "max_qa_iterations exceeded shows 'continue?' modal, not a hard stop (per spec)"
  - "Transcription for Speak button uses existing transcription module; WAV cleaned up after transcribe"

requirements-completed: [CONV-03, CONV-05]

duration: 2min
completed: 2026-02-21
---

# Phase 6 Plan 06: Conversation Dialog and QA Window Summary

**GTK4 post-session analysis dialog and iterative Q&A chat window with confidence-gated finalisation and inline Speak-to-answer recording**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T18:22:50Z
- **Completed:** 2026-02-21T18:24:55Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- ConversationDialog: qualifying questions, editable prompt, save/inject checkboxes, model checkboxes that gray out when API key unconfigured, Submit fires on_submit_cb with all required args
- ConversationQAWindow: scrollable Q&A log, editable AI question field, answer entry, Speak button with AudioRecorder inline, daemon-threaded pipeline calls via GLib.idle_add dispatch
- Confidence >= 0.95 requires explicit user confirmation before finalisation; Done button always shows warning dialog
- _finalise() renames file from _untitled to AI-generated title and fires on_finalised callback

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement ConversationDialog** - `ca0851c` (feat)
2. **Task 2: Implement ConversationQAWindow** - `63f86c8` (feat)

## Files Created/Modified
- `src/linux_speech_flow/conversation_dialog.py` - Post-stop analysis configuration window
- `src/linux_speech_flow/conversation_qa.py` - Iterative AI Q&A chat window

## Decisions Made
- Speak button fills answer entry for user review (not auto-submit) — per CONTEXT.md Claude's Discretion on UX consistency
- Both confidence signal AND user confirmation required before _finalise() runs
- Fallback to ['groq'] if no model checkbox is selected in ConversationDialog
- Speak-transcription uses existing `transcription.transcribe()` function; WAV cleaned up post-transcribe
- max_qa_iterations exceeded → "continue?" modal, not a hard stop

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- ConversationDialog and ConversationQAWindow are ready for integration in App.py (plan 06-07)
- Both windows use Gtk.ApplicationWindow pattern consistent with the rest of the codebase
- ConversationQAWindow expects a ConversationPipeline instance and a save_path from ConversationManager

---
*Phase: 06-conversation-mode*
*Completed: 2026-02-21*
