---
phase: 06-conversation-mode
plan: 01
subsystem: config, hotkey, tray
tags: [config, hotkey, tray, svg, openai, google-genai, conversation-mode]

requires:
  - phase: 05-pipeline-history
    provides: HistoryStore with entry_type + extra_json extensibility columns for Phase 6 conversation records

provides:
  - Phase 6 config defaults (18 keys) merged into DEFAULT_CONFIG via dict-backfill pattern
  - HotkeyManager _STATE_CONVERSATION with F11/F12 dispatch and mutual exclusion
  - tray.py CONV_RECORDING_FRAMES + conv_recording state handler
  - Three conv-recording SVG icons with animated pulsing ring and blue C badge
  - openai>=1.0.0 and google-genai declared in pyproject.toml and installed in venv

affects: [06-02-ConversationRecorder, 06-03-ConversationPipeline, 06-04-ConversationManager]

tech-stack:
  added: [openai>=1.0.0 (installed: 2.21.0), google-genai (installed: 1.64.0)]
  patterns: [Phase-N config dict-merge backfill — no migration code needed for existing user configs]

key-files:
  created:
    - src/linux_speech_flow/icons/linux-speech-flow-conv-recording-1.svg
    - src/linux_speech_flow/icons/linux-speech-flow-conv-recording-2.svg
    - src/linux_speech_flow/icons/linux-speech-flow-conv-recording-3.svg
  modified:
    - src/linux_speech_flow/config.py
    - src/linux_speech_flow/hotkey.py
    - src/linux_speech_flow/tray.py
    - pyproject.toml

key-decisions:
  - "conv_hotkey_start defaults to f11 (not Fn+C): Fn key combos are hardware-firmware intercepted on Linux and never reach the OS input layer; f11 is the practical substitute; Phase 7 makes it configurable"
  - "conv_hotkey_feedback defaults to f12 (not Fn+D): same Fn key Linux limitation"
  - "F11 IDLE-guard: F11 during _STATE_RECORDING is silently ignored (state != _STATE_IDLE), preventing accidental conversation start mid-dictation"
  - "openai upgraded from 0.27.5 to 2.21.0: existing 0.27.5 was system-level; venv now has 1.x API for Grok xAI base_url override"

patterns-established:
  - "Conversation state machine: _STATE_CONVERSATION added alongside _STATE_IDLE/_STATE_RECORDING with strict mutual exclusion"
  - "Conv badge SVG pattern: copy recording-N pulsing ring + add blue circle badge (cx=20,cy=4,r=4.5,fill=#3584E4) with C text, badge opacity varies per frame to create animation"

requirements-completed: [CONV-01, CONV-02]

duration: 3min
completed: 2026-02-21
---

# Phase 06 Plan 01: Conversation Mode Foundation Summary

**Phase 6 scaffold: 18 config defaults, HotkeyManager F11/F12 state machine, tray conv_recording animation with blue-badged SVGs, and openai 2.21.0 + google-genai 1.64.0 installed**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-21T00:04:35Z
- **Completed:** 2026-02-21T00:07:06Z
- **Tasks:** 2
- **Files modified:** 7 (4 modified, 3 created)

## Accomplishments

- Added 18 Phase 6 config keys to DEFAULT_CONFIG covering conversation timing, hotkeys, save directory, feedback mode, AI prompts, qualifying questions, model selection, and viewer dimensions
- Extended HotkeyManager with _STATE_CONVERSATION, three new callback slots, and F11/F12 dispatch with proper IDLE-guard mutual exclusion leaving existing F9/ESC/F10 paths completely unchanged
- Added CONV_RECORDING_FRAMES to tray.py, registered 3 new icon names in ICON_NAMES (total: 11), and wired conv_recording branch in set_state()
- Created three conv-recording SVGs mirroring recording-1/2/3 pulsing animation with blue (#3584E4) "C" badge overlays at varying opacity per frame
- Installed openai 2.21.0 (upgrade from system 0.27.5) and google-genai 1.64.0 in venv

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Phase 6 config defaults and pip dependencies** - `540a3d2` (feat)
2. **Task 2: Extend HotkeyManager and tray for conversation mode** - `158e63b` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/linux_speech_flow/config.py` - Added 18 Phase 6 keys in DEFAULT_CONFIG after Phase 5 block
- `src/linux_speech_flow/hotkey.py` - Added _STATE_CONVERSATION, three callback slots, F11/F12 dispatch, _conv_start/_conv_stop/_conv_feedback_toggle methods
- `src/linux_speech_flow/tray.py` - Added CONV_RECORDING_FRAMES constant, 3 entries in ICON_NAMES, conv_recording branch in set_state()
- `src/linux_speech_flow/icons/linux-speech-flow-conv-recording-1.svg` - Frame 1: small bright ring + blue C badge (opacity 1.0)
- `src/linux_speech_flow/icons/linux-speech-flow-conv-recording-2.svg` - Frame 2: medium fading ring + blue C badge (opacity 0.85)
- `src/linux_speech_flow/icons/linux-speech-flow-conv-recording-3.svg` - Frame 3: large near-transparent ring + blue C badge (opacity 0.70)
- `pyproject.toml` - Added openai>=1.0.0 and google-genai dependencies

## Decisions Made

- conv_hotkey_start defaults to f11 rather than Fn+C: Fn key combos are intercepted by hardware firmware on Linux and never reach the OS input layer. f11 is the practical substitute. Phase 7 will make this configurable via Settings.
- conv_hotkey_feedback defaults to f12 for the same Fn key limitation reason.
- F11 during _STATE_RECORDING is silently ignored (IDLE-guard). Prevents accidental conversation start while dictating.
- openai upgraded from system 0.27.5 to venv 2.21.0 to get the 1.x API required for Grok xAI base_url override pattern.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

pip reported pre-existing system-level conflicts (anthropic 0.3.11, fastapi 0.103.1 with anyio) when installing packages — these are outside the venv and do not affect our installation. Both openai 2.21.0 and google-genai 1.64.0 installed and import cleanly.

## User Setup Required

None - no external service configuration required for this scaffold plan.

## Next Phase Readiness

- Phase 6 config defaults available via load_config() dict-merge backfill — no migration needed
- HotkeyManager ready for ConversationRecorder wiring (plan 06-02) via on_conversation_start/on_conversation_stop callbacks
- tray.py ready to animate conv_recording state when ConversationManager calls set_state('conv_recording')
- openai and google-genai importable for ConversationPipeline (plan 06-03) synthesis backends

---
*Phase: 06-conversation-mode*
*Completed: 2026-02-21*
