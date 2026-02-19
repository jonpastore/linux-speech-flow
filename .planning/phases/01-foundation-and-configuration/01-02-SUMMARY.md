---
phase: 01-foundation-and-configuration
plan: "02"
subsystem: infra
tags: [python, json, pathlib, xdg, config, tdd, pytest]

requires:
  - phase: 01-foundation-and-configuration/01-01
    provides: Installable linux_speech_flow package with src/ layout (import works)

provides:
  - load_config() returning dict merged over DEFAULT_CONFIG from XDG config JSON
  - save_config() writing pretty JSON with 0600 permissions and parent dir creation
  - CONFIG_PATH at ~/.config/linux-speech-flow/config.json
  - DEFAULT_CONFIG with groq_api_key, microphone, vocabulary (list), setup_complete (bool)
  - 10-test pytest suite covering all behaviors

affects:
  - 01-03 (API key module reads/writes groq_api_key via config)
  - 01-04 (GTK wizard reads setup_complete to gate wizard display; writes config on completion)
  - 01-05 (Settings window reads/writes config for hotkey, microphone, vocabulary)
  - All phases that need persistent user settings

tech-stack:
  added:
    - pytest>=9.0 (test runner, installed in .venv)
  patterns:
    - _path keyword-only parameter for test injection without breaking production API
    - config.update(file_data) over DEFAULT_CONFIG copy for safe partial config merging
    - os.chmod(path, 0o600) after json.dump for secure config file permissions

key-files:
  created:
    - src/linux_speech_flow/config.py
    - tests/__init__.py
    - tests/test_config.py
  modified: []

key-decisions:
  - "_path keyword-only parameter used for test injection: allows monkeypatching without touching module globals, keeps production API clean (no path arg required)"
  - "config.update() merge pattern: load DEFAULT_CONFIG copy then update with file data ensures all keys always present even for old/partial config files"
  - "pytest installed in .venv (not dev-depends in pyproject.toml): keeps test tooling separate from production package dependencies"

patterns-established:
  - "Test injection via _path=: keyword-only default param lets tests pass tmp_path without changing production call sites"
  - "Permissions after write: os.chmod called after json.dump, not before, to avoid TOCTOU race where file exists but is not yet 0600"

requirements-completed: [CONF-03, CONF-04]

duration: 2min
completed: 2026-02-19
---

# Phase 1 Plan 02: Config Persistence Summary

**XDG JSON config module with load/save, 0o600 permissions, vocabulary as string list, and setup_complete flag — 10 TDD tests all passing**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T06:54:46Z
- **Completed:** 2026-02-19T06:56:04Z
- **Tasks:** 1 (TDD: RED + GREEN, no refactor needed)
- **Files modified:** 3

## Accomplishments

- `load_config()` returns `DEFAULT_CONFIG` copy when no file exists, merges file data over defaults for partial configs
- `save_config()` creates parent dirs, writes pretty JSON, sets `0o600` permissions atomically
- 10 pytest tests covering all specified behaviors — all pass

## Task Commits

TDD commits:

1. **RED - Failing tests** - `099f7fd` (test)
2. **GREEN - Implementation** - `91547a9` (feat)

**Plan metadata:** (docs commit - see below)

_Note: No REFACTOR commit needed — implementation was minimal and clean._

## Files Created/Modified

- `src/linux_speech_flow/config.py` - load_config/save_config with DEFAULT_CONFIG, CONFIG_PATH, _path injection
- `tests/__init__.py` - Package marker for pytest discovery
- `tests/test_config.py` - 10 tests: defaults, round-trip, permissions, partial merge, vocab list, bool type, XDG path

## Decisions Made

- Used `_path` keyword-only parameter for test injection rather than monkeypatching module globals. Cleaner API: production callers never pass it, tests use `tmp_path` directly.
- `config.update(file_data)` over a `dict(DEFAULT_CONFIG)` copy ensures partial/legacy config files always return all keys without KeyError.
- Installed pytest directly in `.venv` rather than adding as `[dev]` optional dependency in pyproject.toml — keeps production package requirements minimal for .deb packaging.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing pytest test runner**
- **Found during:** TDD setup (before RED phase)
- **Issue:** pytest not installed in .venv; `python -m pytest` returned `No module named pytest`
- **Fix:** Ran `.venv/bin/pip install pytest` (installed pytest-9.0.2)
- **Files modified:** .venv (not tracked in git)
- **Verification:** `python -m pytest --version` returns `pytest 9.0.2`
- **Committed in:** Implicit in test infrastructure setup

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for test execution. No scope creep.

## Issues Encountered

None beyond the pytest installation deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `config.py` ready for import by wizard (01-04), API key module (01-03), and settings window (01-05)
- `load_config()` / `save_config()` API is stable and tested
- `setup_complete=False` default will trigger wizard display in 01-04
- Test suite established — future plans can add tests alongside implementation
- No blockers for Plan 03

## Self-Check: PASSED

- FOUND: src/linux_speech_flow/config.py
- FOUND: tests/__init__.py
- FOUND: tests/test_config.py
- FOUND: 01-02-SUMMARY.md
- FOUND: 099f7fd (RED commit)
- FOUND: 91547a9 (GREEN commit)
- Tests: 10 passed in 0.02s

---
*Phase: 01-foundation-and-configuration*
*Completed: 2026-02-19*
