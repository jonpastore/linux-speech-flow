---
phase: 01-foundation-and-configuration
plan: "04"
subsystem: ui
tags: [gtk4, gtk.stack, pygobject, wizard, settings, threading, glib]

requires:
  - phase: 01-foundation-and-configuration plan 01
    provides: Gtk.Application base, audio.list_microphones(), venv with system-site-packages gi
  - phase: 01-foundation-and-configuration plan 02
    provides: config.py with load_config/save_config, setup_complete field, DEFAULT_CONFIG
  - phase: 01-foundation-and-configuration plan 03
    provides: groq_client.validate_api_key() returning {ok, message} dict

provides:
  - WizardWindow (Gtk.ApplicationWindow) with 3-page Gtk.Stack: API key, microphone, vocabulary
  - SettingsWindow (Gtk.Window) with flat layout: API key + mic + vocabulary + Save button
  - app.py do_activate branching on setup_complete: wizard on first run, placeholder with Settings access after
  - Full startup sequence: wizard flow saves config with setup_complete=True

affects:
  - Phase 4 tray implementation (replaces placeholder window with real AppIndicator tray)
  - Phase 2 audio pipeline (wizard mic selection feeds into recording config)

tech-stack:
  added: []
  patterns:
    - "Gtk.Stack for multi-page wizard (NOT Gtk.Assistant — deprecated GTK4.10, removed GTK5)"
    - "threading.Thread(daemon=True) + GLib.idle_add(callback) for background validation → UI update"
    - "Gtk.PasswordEntry(show_peek_icon=True) for API key fields (built-in masking)"
    - "list_microphones() called on page/window entry (not at init) for re-enumeration support"

key-files:
  created:
    - src/linux_speech_flow/wizard.py
    - src/linux_speech_flow/settings.py
  modified:
    - src/linux_speech_flow/app.py

key-decisions:
  - "Flat layout for SettingsWindow (not wizard with settings_mode flag) — simpler, no wizard nav state needed"
  - "Microphone enumeration deferred to page/window entry (not __init__) to support re-enumeration on re-open"
  - "Validate button in both wizard and settings uses same threading+GLib.idle_add pattern for UI thread safety"

patterns-established:
  - "GLib.idle_add callback must return False to avoid being re-called"
  - "pulsectl.PulseError caught in enumerate_microphones, shown as inline label (not dialog)"
  - "Wizard close without Finish leaves setup_complete=False — enforced by not calling save_config in close handler"

requirements-completed: [CONF-01, CONF-02, CONF-04, CONF-05]

duration: 3min
completed: 2026-02-19
---

# Phase 1 Plan 04: GTK Wizard and Settings Window Summary

**GTK4 multi-step setup wizard (Gtk.Stack: API key + microphone + vocabulary) and flat settings window with background thread API key validation and app.py startup sequence gating on setup_complete**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T07:02:21Z
- **Completed:** 2026-02-19T07:05:36Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- WizardWindow with 3-page Gtk.Stack (api_key, microphone, vocabulary), Back/Next/Finish navigation
- API key validation in daemon thread with GLib.idle_add for UI thread safety; spinner + disabled Next during validation
- SettingsWindow flat layout re-enumerating microphones on open; save writes config without changing setup_complete
- app.py do_activate branches on setup_complete: first-run wizard, post-setup placeholder with Open Settings button

## Task Commits

Each task was committed atomically:

1. **Task 1: Multi-step wizard (Gtk.Stack)** - `dffe363` (feat)
2. **Task 2: Settings window and app.py startup sequence** - `726c4c4` (feat)

## Files Created/Modified

- `src/linux_speech_flow/wizard.py` - WizardWindow with 3-page Gtk.Stack, threading validation, save_config on Finish
- `src/linux_speech_flow/settings.py` - SettingsWindow flat layout, load_config on open, list_microphones on open, save_config on Save
- `src/linux_speech_flow/app.py` - do_activate with setup_complete branch, _on_wizard_closed handler, placeholder window with Settings button

## Decisions Made

- Chose flat layout for SettingsWindow over reusing WizardWindow with `settings_mode=True` — the flat layout has no wizard navigation state to manage, simpler code path
- Microphone enumeration deferred to page entry (not wizard `__init__`) to support re-enumeration if audio devices change between runs
- Validation threading pattern identical between wizard and settings: daemon thread + GLib.idle_add returning False

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Full startup sequence in place: wizard → config saved → tray (Phase 4)
- All six modules import cleanly together: app, wizard, settings, config, audio, groq_client
- All 22 existing tests still pass (0 regressions)
- Phase 1 is now complete (5 of 5 plans done): foundation, config TDD, API validation TDD, GTK UI
- Phase 4 tray work can replace `_build_placeholder_window()` with real AppIndicator implementation

---
*Phase: 01-foundation-and-configuration*
*Completed: 2026-02-19*
