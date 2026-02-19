---
phase: 02-audio-capture-and-hotkey
plan: "02"
subsystem: audio
tags: [wav, paplay, notify-send, importlib-resources, subprocess, pulseaudio]

requires:
  - phase: 01-foundation-and-configuration
    provides: pyproject.toml with package-data config for sounds/*.wav

provides:
  - Three bundled WAV files (start.wav, stop.wav, error.wav) in linux_speech_flow/sounds/
  - play_sound() non-blocking paplay wrapper via importlib.resources
  - send_notification() notify-send wrapper returning notification ID for replace-chain

affects:
  - 02-04-hotkey-manager (uses play_sound for F9 press/release feedback)
  - 02-05-integration (uses send_notification for Recording/Transcribing states)
  - 03-transcription (uses send_notification replace-chain)

tech-stack:
  added: []
  patterns:
    - importlib.resources.files() for bundled asset path resolution (works in .deb/wheel)
    - subprocess.Popen for non-blocking audio playback
    - subprocess.run with timeout=2 for synchronous notification ID capture

key-files:
  created:
    - src/linux_speech_flow/sounds/__init__.py
    - src/linux_speech_flow/sounds/start.wav
    - src/linux_speech_flow/sounds/stop.wav
    - src/linux_speech_flow/sounds/error.wav
    - src/linux_speech_flow/notify.py
    - src/linux_speech_flow/scripts/__init__.py
    - src/linux_speech_flow/scripts/generate_sounds.py
  modified: []

key-decisions:
  - "play_sound() moved into sounds/__init__.py instead of sounds.py — Python cannot have both a sounds.py module and sounds/ package in the same directory"
  - "importlib.resources.files() used for WAV path resolution (not __file__) for .deb/wheel compatibility"
  - "subprocess.Popen for paplay (non-blocking); subprocess.run for notify-send (synchronous ID capture)"
  - "send_notification returns None gracefully when notify-send missing or -p unsupported"

patterns-established:
  - "Bundled assets: use importlib.resources.files('pkg.subpkg').joinpath(name) with as_file() context manager"
  - "Non-blocking audio: subprocess.Popen with stderr=DEVNULL — never catch FileNotFoundError"
  - "Notification replace-chain: send_notification returns int ID; subsequent calls pass replace_id="

requirements-completed: [CORE-04]

duration: 2min
completed: 2026-02-19
---

# Phase 02 Plan 02: Audio Feedback (Sounds + Notifications) Summary

**Bundled WAV sound files (start/stop/error chimes) with non-blocking paplay wrapper and notify-send notification module supporting ID-based replace-chain**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T13:34:31Z
- **Completed:** 2026-02-19T13:36:31Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Generated 3 bundled WAV files: ascending chime (start), descending chime (stop), triple buzz (error)
- play_sound() resolves bundled paths via importlib.resources (works in installed .deb/wheel packages)
- send_notification() captures notify-send -p ID for Phase 3's Recording->Transcribing replace-chain
- All 22 existing tests continue passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Generate bundled WAV sound files** - `750b7eb` (feat)
2. **Task 2: sounds.py and notify.py utility modules** - `4de8d47` (feat)

## Files Created/Modified
- `src/linux_speech_flow/sounds/__init__.py` - play_sound() module (also makes sounds/ a package for importlib.resources)
- `src/linux_speech_flow/sounds/start.wav` - Ascending chime 440->880Hz, 0.3s, mono 22050Hz 16-bit
- `src/linux_speech_flow/sounds/stop.wav` - Descending chime 880->440Hz, 0.3s, mono 22050Hz 16-bit
- `src/linux_speech_flow/sounds/error.wav` - Triple 200Hz buzz with gaps, ~0.45s, mono 22050Hz 16-bit
- `src/linux_speech_flow/notify.py` - send_notification() with -p flag for ID capture
- `src/linux_speech_flow/scripts/__init__.py` - Makes scripts/ a package
- `src/linux_speech_flow/scripts/generate_sounds.py` - Dev tool for regenerating WAV files

## Decisions Made
- play_sound() placed in sounds/__init__.py (not sounds.py): Python raises ImportError when both sounds.py module and sounds/ package exist in same directory; moving play_sound into __init__.py resolves the collision while keeping the import path `from linux_speech_flow.sounds import play_sound` unchanged
- importlib.resources.files() used for bundled WAV resolution (not __file__-relative) for correct behavior in installed .deb packages
- subprocess.Popen (non-blocking) for paplay; subprocess.run with timeout=2 (synchronous) for notify-send

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Resolved naming collision between sounds.py and sounds/ package**
- **Found during:** Task 2 (sounds.py and notify.py utility modules)
- **Issue:** Python cannot have both `sounds.py` module and `sounds/` directory package under the same parent; `from linux_speech_flow.sounds import play_sound` raised ImportError because the package (directory) shadowed the module file
- **Fix:** Placed play_sound() implementation directly in sounds/__init__.py; removed the separate sounds.py file. Import path `from linux_speech_flow.sounds import play_sound` works identically from the caller's perspective
- **Files modified:** src/linux_speech_flow/sounds/__init__.py (replaced empty __init__.py)
- **Verification:** Imports ok and enabled=False no-op both confirmed; 22 tests pass
- **Committed in:** 4de8d47 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Auto-fix required for correctness. All must_have truths satisfied. No scope creep.

## Issues Encountered
- Naming collision between sounds.py and sounds/ package — see Deviations section above

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- play_sound() and send_notification() ready for HotkeyManager (Plan 04) and integration (Plan 05)
- WAV files bundled and accessible via importlib.resources in both dev and installed modes
- No blockers for subsequent plans

---
*Phase: 02-audio-capture-and-hotkey*
*Completed: 2026-02-19*

## Self-Check: PASSED

All created files confirmed present on disk. Both task commits (750b7eb, 4de8d47) verified in git history.
