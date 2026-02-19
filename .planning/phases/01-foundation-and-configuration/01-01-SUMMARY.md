---
phase: 01-foundation-and-configuration
plan: "01"
subsystem: infra
tags: [python, gtk4, pygobject, pulsectl, setuptools, pipewire, pulseaudio]

requires: []

provides:
  - Installable Python package via pip install -e . with src/ layout
  - linux-speech-flow CLI entry point wired to Gtk.Application
  - Gtk.Application subclass with D-Bus single-instance enforcement (FLAGS_NONE)
  - list_microphones() returning name/description dicts, monitor sources excluded
  - System-site-packages venv for PyGObject/GTK4 access without building from source

affects:
  - 01-02 (config module imports from this package)
  - 01-03 (API key module imports from this package)
  - 01-04 (GTK wizard imports App from app.py)
  - All subsequent phases (all modules live in linux_speech_flow package)

tech-stack:
  added:
    - setuptools>=68 (build backend)
    - requests>=2.31 (HTTP for Groq API)
    - pulsectl>=24.0 (PulseAudio/PipeWire microphone enumeration)
    - PyGObject/gi (system package, Python 3.10 via --system-site-packages)
    - GTK4 (via PyGObject gi.repository.Gtk version 4.0)
  patterns:
    - src/ layout with setuptools auto-discovery
    - Gtk.Application subclass as application root (D-Bus single-instance via FLAGS_NONE)
    - pulsectl context manager for per-call PulseAudio connection lifecycle

key-files:
  created:
    - pyproject.toml
    - src/linux_speech_flow/__init__.py
    - src/linux_speech_flow/__main__.py
    - src/linux_speech_flow/app.py
    - src/linux_speech_flow/audio.py
  modified: []

key-decisions:
  - "Python 3.10 (system) used for venv instead of pyenv 3.11: gi/PyGObject is compiled for system Python 3.10 only; pyenv 3.11 cannot access system gi without libgirepository1.0-dev build"
  - "requires-python set to >=3.10 (not >=3.11 as planned) to match system Python with gi bindings"
  - "pulsectl context manager per call: safe for re-enumeration on Settings re-open, no long-lived connection"
  - "FLAGS_NONE for single-instance: second launch triggers activate on first instance then exits automatically via D-Bus"

patterns-established:
  - "Venv creation: /usr/bin/python3.10 -m venv --system-site-packages .venv for gi access"
  - "Package entry point: Gtk.Application.run(sys.argv) returns exit code from main()"

requirements-completed: [CONF-02, CONF-05]

duration: 3min
completed: 2026-02-19
---

# Phase 1 Plan 01: Project Scaffold Summary

**Python package with Gtk.Application single-instance entry point and pulsectl microphone enumeration via PulseAudio/PipeWire**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T06:48:04Z
- **Completed:** 2026-02-19T06:51:41Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Installable Python package (pip install -e .) with src/ layout using setuptools auto-discovery
- GTK4 application entry point with D-Bus single-instance enforcement (second launch silently exits)
- PulseAudio/PipeWire microphone enumeration excluding monitor/loopback sources

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffold and pyproject.toml** - `9260793` (feat)
2. **Task 2: Audio device enumeration module** - `25205dc` (feat)

**Plan metadata:** (docs commit - see below)

## Files Created/Modified

- `pyproject.toml` - Package definition, entry point, dependencies (requests, pulsectl)
- `src/linux_speech_flow/__init__.py` - Package marker (empty)
- `src/linux_speech_flow/__main__.py` - Enables python -m linux_speech_flow
- `src/linux_speech_flow/app.py` - Gtk.Application subclass with FLAGS_NONE, do_activate stub, main()
- `src/linux_speech_flow/audio.py` - list_microphones() via pulsectl, filters .monitor sources

## Decisions Made

- Used Python 3.10 (system) for venv base instead of pyenv Python 3.11. PyGObject/gi is compiled only for the system Python 3.10; libgirepository1.0-dev is not installed, blocking a from-source build for 3.11. pyproject.toml `requires-python` updated to `>=3.10` accordingly.
- Confirmed pulsectl per-call context manager pattern (no long-lived connection) for safe re-enumeration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted requires-python from >=3.11 to >=3.10**
- **Found during:** Task 1 (venv creation)
- **Issue:** pyenv Python 3.11 cannot access system gi/PyGObject module (compiled for CPython 3.10). `libgirepository1.0-dev` not installed, blocking pip build of PyGObject for 3.11. Using pyenv 3.11 as venv base would mean no GTK4 access.
- **Fix:** Created venv with `/usr/bin/python3.10 --system-site-packages`; updated `requires-python = ">=3.10"` in pyproject.toml
- **Files modified:** pyproject.toml
- **Verification:** `import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk` succeeds in venv
- **Committed in:** `9260793` (Task 1 commit)

**2. [Rule 3 - Blocking] Upgraded pip in venv before install**
- **Found during:** Task 1 (pip install -e .)
- **Issue:** System pip 22.0.2 lacks `build_editable` hook support required for modern setuptools editable installs
- **Fix:** Ran `.venv/bin/pip install --upgrade pip` (22.0.2 -> 26.0.1) before installing the package
- **Files modified:** .venv (not tracked in git)
- **Verification:** `pip install -e .` succeeds after upgrade
- **Committed in:** `9260793` (implicit in task)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes necessary for GTK access and installability. No scope creep. Python 3.10 is fully supported; all Phase 1+ plans will work correctly.

## Issues Encountered

- pyenv Python 3.11 not usable as venv base because system gi bindings only exist for Python 3.10. Resolved by switching to system Python 3.10 with --system-site-packages.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Package scaffold ready for Plan 02 (config persistence TDD)
- All imports working: `from linux_speech_flow.app import main`, `from linux_speech_flow.audio import list_microphones`
- 2 microphones found on this system (built-in + SteelSeries Arctis Nova 7)
- No blockers for Plan 02

---
*Phase: 01-foundation-and-configuration*
*Completed: 2026-02-19*
