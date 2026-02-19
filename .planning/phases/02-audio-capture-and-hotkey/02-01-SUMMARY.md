---
phase: 02-audio-capture-and-hotkey
plan: "01"
subsystem: audio
tags: [pynput, pasimple, pulsectl, config, audio]

requires:
  - phase: 01-foundation
    provides: config.py with DEFAULT_CONFIG and load_config(), audio.py with list_microphones()

provides:
  - pynput>=1.8 and pasimple>=0.0.3 installed and declared in pyproject.toml
  - sounds/*.wav package-data glob in pyproject.toml
  - Four Phase 2 config defaults: sounds_enabled, sounds_output_device, max_recording_duration, silence_stop_duration
  - audio.list_sinks() returning PulseAudio output sinks as list of dicts, swallowing PulseError

affects: [02-02, 02-03, 02-04, 02-05]

tech-stack:
  added: [pynput>=1.8, pasimple>=0.0.3]
  patterns: [PulseError swallowed in list_sinks() for graceful degradation (contrast: list_microphones raises)]

key-files:
  created: []
  modified:
    - pyproject.toml
    - src/linux_speech_flow/config.py
    - src/linux_speech_flow/audio.py
    - tests/test_config.py

key-decisions:
  - "list_sinks() swallows PulseError and returns [] — sounds system degrades to PulseAudio default sink rather than failing"
  - "No config migration code needed — load_config() dict merge pattern already handles Phase 1 configs gaining Phase 2 defaults"
  - "test_save_load_round_trip updated to assert saved keys are present (not strict equality) — correct contract for a config that merges defaults"

patterns-established:
  - "Graceful degradation pattern: output enumeration returns [] on PulseError; input enumeration raises (intentional asymmetry)"
  - "DEFAULT_CONFIG merge pattern: new keys added to DEFAULT_CONFIG automatically backfill older config.json files"

requirements-completed: [CORE-01, CORE-02, CORE-03, CORE-04, CORE-05]

duration: 2min
completed: 2026-02-19
---

# Phase 2 Plan 01: Phase 2 Foundation Summary

**pynput+pasimple deps added to pyproject.toml, four Phase 2 config defaults in DEFAULT_CONFIG, and list_sinks() output sink enumeration in audio.py**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T13:34:23Z
- **Completed:** 2026-02-19T13:36:22Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added pynput>=1.8 and pasimple>=0.0.3 to pyproject.toml and installed into project venv
- Added sounds/*.wav package-data glob for WAV bundling in .deb installs
- Extended DEFAULT_CONFIG with four Phase 2 keys (sounds_enabled, sounds_output_device, max_recording_duration, silence_stop_duration)
- Implemented list_sinks() in audio.py with graceful PulseError degradation

## Task Commits

Each task was committed atomically:

1. **Task 1: pyproject.toml — add deps and sounds package data** - `069121b` (chore)
2. **Task 2: config.py Phase 2 defaults; audio.py list_sinks()** - `1fe26d5` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified
- `pyproject.toml` - Added pynput>=1.8, pasimple>=0.0.3 deps; added sounds/*.wav package-data section
- `src/linux_speech_flow/config.py` - Added four Phase 2 keys to DEFAULT_CONFIG
- `src/linux_speech_flow/audio.py` - Added list_sinks() function after list_microphones()
- `tests/test_config.py` - Updated test_save_load_round_trip to reflect new default-merge contract

## Decisions Made
- list_sinks() swallows PulseError and returns [] rather than raising — sounds system will fall back to PulseAudio default sink, making audio playback resilient to sink enumeration failures
- No migration code needed — the existing dict merge in load_config() means Phase 1 config.json files automatically receive Phase 2 defaults on next load
- test_save_load_round_trip updated from strict equality to key-presence check — the correct contract is that all saved values are preserved AND all DEFAULT_CONFIG keys are present

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_save_load_round_trip for new default-merge contract**
- **Found during:** Task 2 (config.py Phase 2 defaults)
- **Issue:** Test asserted `result == cfg` where cfg was a Phase 1-style 4-key dict; after adding Phase 2 defaults, load_config() now returns 8 keys for any loaded config, correctly by design
- **Fix:** Changed assertion to verify all saved keys are present with correct values AND all DEFAULT_CONFIG keys are present — matches the documented contract
- **Files modified:** tests/test_config.py
- **Verification:** All 22 tests pass
- **Committed in:** 1fe26d5 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Test fix necessary for correctness — the test was written against the old 4-key schema; no scope creep.

## Issues Encountered
None beyond the test fix above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- pynput and pasimple available in .venv for recorder.py and hotkey.py
- Phase 2 config defaults ready; settings UI (02-04) can expose these keys
- list_sinks() ready for sounds settings UI (02-04) sink picker
- All 22 pre-existing tests pass — no regressions

---
*Phase: 02-audio-capture-and-hotkey*
*Completed: 2026-02-19*

## Self-Check: PASSED

All artifacts verified:
- FOUND: pyproject.toml
- FOUND: config.py
- FOUND: audio.py
- FOUND: SUMMARY.md
- FOUND: commit 069121b
- FOUND: commit 1fe26d5
