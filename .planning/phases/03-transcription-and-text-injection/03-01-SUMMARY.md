---
phase: 03-transcription-and-text-injection
plan: "01"
subsystem: foundation
tags: [config, sounds, groq, requirements]
dependency_graph:
  requires: []
  provides: [Phase3ConfigDefaults, ProcessingSound, SuccessSound, GroqDependency, RequirementsDoc]
  affects: [03-02-PLAN.md, 03-03-PLAN.md, 03-04-PLAN.md, 03-05-PLAN.md, 03-06-PLAN.md]
tech_stack:
  added: [groq>=1.0.0]
  patterns: [DEFAULT_CONFIG dict merge backfill, WAV tone generation via stdlib wave+struct]
key_files:
  created:
    - src/linux_speech_flow/sounds/processing.wav
    - src/linux_speech_flow/sounds/success.wav
    - REQUIREMENTS.md
  modified:
    - src/linux_speech_flow/config.py
    - src/linux_speech_flow/scripts/generate_sounds.py
    - pyproject.toml
decisions:
  - "groq>=1.0.0 declared in pyproject.toml — covers Whisper transcription and LLM post-processing via single SDK"
  - "Phase 3 config keys use dict merge backfill — no migration code needed for existing user configs"
  - "processing.wav uses C5->E5 (ascending two-note) for 'starting work'; success.wav uses C5->E5->G5 (three-note fanfare) for distinct completion sound"
metrics:
  duration: 1 min
  completed: 2026-02-20T03:51:34Z
  tasks_completed: 2
  files_modified: 6
---

# Phase 3 Plan 01: Phase 3 Foundation — Config, Sounds, and Requirements Summary

Phase 3 foundation established: groq SDK declared, seven new config defaults backfilled automatically into existing configs, two new WAV sound files generated, and all 11 TRANS requirements documented in REQUIREMENTS.md.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Phase 3 config defaults and groq dependency | 50d8e73 | config.py, pyproject.toml |
| 2 | Generate processing/success sounds and REQUIREMENTS.md | 3e6b7d8 | generate_sounds.py, processing.wav, success.wav, REQUIREMENTS.md |

## What Was Built

### Config Defaults (config.py)

Seven new keys added to `DEFAULT_CONFIG`:
- `whisper_model`: "whisper-large-v3-turbo" — Groq Whisper model identifier
- `llm_model`: "meta-llama/llama-4-scout-17b-16e-instruct" — Groq LLM for post-processing
- `pipeline_timeout`: 60 — seconds before pipeline is considered hung
- `processing_sound_enabled`: True — one-shot chime on pipeline start
- `success_sound_enabled`: True — fanfare on successful paste
- `app_categories`: dict with "terminals" and "editors" lists for paste-mode selection
- `llm_system_prompt`: full system prompt for LLM cleanup instructions

All keys backfill automatically via `load_config()`'s existing `config.update(data)` merge — no migration needed.

### Groq SDK (pyproject.toml)

`groq>=1.0.0` added to `dependencies`. Single SDK handles both Whisper audio transcription and LLM chat completions.

### Sound Files

- `processing.wav`: C5 (523 Hz, 0.1s) + E5 (659 Hz, 0.1s) — ascending two-note "starting work" indicator
- `success.wav`: C5 (523 Hz, 0.1s) + E5 (659 Hz, 0.1s) + G5 (784 Hz, 0.15s) — three-note ascending fanfare for paste completion

Both generated via existing `generate_sounds.py` script using stdlib `wave`+`struct` (no external dependencies).

### REQUIREMENTS.md

Created at repo root with all requirements across 6 categories: CONF (5), CORE (5), TRANS (11), TRAY (4), HIST (3), DIST (5). Phase 1 and 2 requirements marked complete; all Phase 3 TRANS requirements (TRANS-01 through TRANS-11) defined as unchecked.

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

All 22 existing tests pass. Config correctly returns all Phase 3 keys from `load_config()`. Both WAV files present with 22050 Hz sample rate. groq>=1.0.0 present in pyproject.toml. REQUIREMENTS.md contains TRANS-07 through TRANS-11.

## Self-Check: PASSED
