---
phase: 06-conversation-mode
plan: 03
subsystem: ai
tags: [groq, openai, gemini, concurrent, json-mode, transcription, analysis]

requires:
  - phase: 06-01
    provides: config keys for conv_groq_model, grok_api_key, grok_model, gemini_api_key, gemini_model, conv_meta_model
  - phase: 06-02
    provides: ConversationRecorder producing WAV chunk files for transcribe_chunk()

provides:
  - ConversationPipeline class with transcribe_chunk, analyze, synthesize, continue_qa
  - ANALYSIS_SYSTEM_PROMPT constant (JSON schema for multi-model analysis)
  - conv_filename() for ISO8601T-timestamped conversation file naming
  - coalesce_file() for writing structured conversation markdown files

affects: [06-04-ConversationManager, 06-06-QAWindow]

tech-stack:
  added: []
  patterns:
    - "ThreadPoolExecutor parallel model fan-out with per-future exception isolation"
    - "Deferred imports inside call methods (_call_grok, _call_gemini) to avoid startup cost when keys not configured"
    - "JSON-mode API calls (response_format={type:json_object}) for deterministic structured output"
    - "_parse_result defensive parsing with safe defaults for non-JSON responses"

key-files:
  created:
    - src/linux_speech_flow/conversation_pipeline.py
  modified: []

key-decisions:
  - "Deferred openai/google.genai imports inside _call_grok/_call_gemini — avoids ImportError at startup when those packages not installed or keys not configured"
  - "Single _parse_result method handles all three model call results — consistent safe-defaults for non-JSON or malformed responses"
  - "synthesize() falls back to first non-error model result if meta-model call fails — prevents total analysis failure"
  - "continue_qa() delegates to analyze() with qa_context as both qualifying_answers and updated_prompt — keeps Q&A rounds in same ThreadPoolExecutor fan-out path"
  - "coalesce_file() omits ## Q&A section entirely when qa_rounds is empty — no empty headers in output file"

patterns-established:
  - "ConversationPipeline.analyze() is the single entry point for all AI analysis, regardless of model count"
  - "model_results dict keys are model names ('groq', 'grok', 'gemini') — consistent throughout pipeline"

requirements-completed: [CONV-03, CONV-04, CONV-05]

duration: 1min
completed: 2026-02-21
---

# Phase 6 Plan 03: ConversationPipeline Summary

**Multi-model AI analysis engine with parallel Groq/Grok/Gemini fan-out, JSON-mode structured output, and meta-model synthesis via ThreadPoolExecutor**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-21T18:12:33Z
- **Completed:** 2026-02-21T18:13:51Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- ConversationPipeline with transcribe_chunk (Groq Whisper), analyze (parallel multi-model), synthesize (meta-model merge), continue_qa (Q&A round refinement)
- ThreadPoolExecutor fan-out fires all selected models simultaneously with 90s per-future timeout and per-model exception isolation
- All three model backends (_call_groq, _call_grok, _call_gemini) use JSON mode for deterministic structured output
- conv_filename() produces ISO8601T-timestamped safe-title filenames; coalesce_file() writes markdown with conditional Q&A section

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement ConversationPipeline** - `c3b81d7` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/linux_speech_flow/conversation_pipeline.py` - ConversationPipeline class, ANALYSIS_SYSTEM_PROMPT, conv_filename, coalesce_file

## Decisions Made

- Deferred openai/google.genai imports inside _call_grok/_call_gemini to avoid startup cost when keys not configured
- synthesize() fallback picks first non-error model result if meta-model call fails entirely
- coalesce_file() omits ## Q&A header when qa_rounds is empty (no empty sections in output files)
- continue_qa() delegates to analyze() to keep Q&A rounds in the same ThreadPoolExecutor fan-out path

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ConversationPipeline API is complete and importable — ConversationManager (06-04) can call transcribe_chunk() and analyze()
- Q&A window (06-06) can call continue_qa() to feed user answers back for analysis refinement
- coalesce_file() ready for ConversationManager to write final conversation files to conv_save_dir

---
*Phase: 06-conversation-mode*
*Completed: 2026-02-21*
