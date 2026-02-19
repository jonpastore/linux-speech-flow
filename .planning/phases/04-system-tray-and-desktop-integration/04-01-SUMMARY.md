---
phase: 04-system-tray-and-desktop-integration
plan: 01
subsystem: ui
tags: [trayer, dbus, svg, gtk4, system-tray, xdg-icons, animation, StatusNotifierItem]

requires:
  - phase: 03-transcription-and-text-injection
    provides: TranscriptionPipeline and app.py structure that TrayManager will be wired into

provides:
  - TrayManager class with 4-state icon animation (idle, recording, processing, error)
  - install_icons() function to copy bundled SVGs to XDG hicolor theme at runtime
  - 8 bundled SVG icons as package data in icons/
  - trayer==0.1.1 dependency for GTK4-compatible StatusNotifierItem tray

affects:
  - 04-02 (app.py wiring of TrayManager to pipeline states)
  - 04-03 (autostart desktop file uses freeflow-idle icon name)

tech-stack:
  added:
    - trayer==0.1.1 (StatusNotifierItem D-Bus tray, GTK4-compatible)
    - importlib.resources (bundled icon extraction, same pattern as sounds/)
  patterns:
    - GLib.timeout_add for frame-swapping animation (returns True to continue)
    - dbus.mainloop.glib.DBusGMainLoop set at __init__ before any D-Bus objects
    - Dict mutation before update_menu() for dynamic menu items (pitfall 5 avoidance)
    - install_icons() always overwrites so icon updates propagate on restart

key-files:
  created:
    - src/linux_speech_flow/tray.py
    - src/linux_speech_flow/icons/__init__.py
    - src/linux_speech_flow/icons/freeflow-idle.svg
    - src/linux_speech_flow/icons/freeflow-recording-1.svg
    - src/linux_speech_flow/icons/freeflow-recording-2.svg
    - src/linux_speech_flow/icons/freeflow-recording-3.svg
    - src/linux_speech_flow/icons/freeflow-processing-1.svg
    - src/linux_speech_flow/icons/freeflow-processing-2.svg
    - src/linux_speech_flow/icons/freeflow-processing-3.svg
    - src/linux_speech_flow/icons/freeflow-error.svg
  modified:
    - pyproject.toml

key-decisions:
  - "trayer==0.1.1 pins the library version — SNI protocol is stable even if wrapper updates"
  - "install_icons() always overwrites (no exists check) so icon updates propagate on app restart"
  - "DBusGMainLoop set in TrayManager.__init__ (not module level) to control initialization order"
  - "Left-click opens Settings (trayer SNI: right-click always shows menu, cannot redirect to Settings)"

patterns-established:
  - "Animation: GLib.timeout_add returns source_id; always call _stop_animation() before _start_animation() to prevent stacked timers"
  - "Menu mutation: mutate dict reference first, then call update_menu() — update_menu() re-fetches from menu_items"
  - "GLib.idle_add convention: update_failed_count returns False to avoid re-invocation"

requirements-completed: [TRAY-01, TRAY-02]

duration: 1min
completed: 2026-02-21
---

# Phase 04 Plan 01: TrayManager with 8-SVG icon set and GLib animation state machine

**TrayManager class using trayer 0.1.1 (StatusNotifierItem D-Bus) with 4-state icon animation, 8 bundled XDG SVG icons installable to hicolor theme, and a dynamic menu with live failed-count item.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-21T11:11:37Z
- **Completed:** 2026-02-21T11:13:24Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Created icons/ package with 8 SVGs (idle grey, recording red pulse x3, processing yellow arc x3, error red X) as installable package data
- Created TrayManager with full state machine (idle/recording/processing/error), GLib timer animation, and trayer SNI integration
- install_icons() copies all 8 SVGs to ~/.local/share/icons/hicolor/scalable/status/ at startup; GTK icon lookup resolves by name

## Task Commits

1. **Task 1: Create icons/ package with 8 SVG icons and update pyproject.toml** - `e27c9fd` (feat)
2. **Task 2: Create tray.py with TrayManager** - `4491311` (feat)

## Files Created/Modified

- `src/linux_speech_flow/tray.py` - TrayManager class: set_state(), update_failed_count(), setup(), install_icons(), animation helpers
- `src/linux_speech_flow/icons/__init__.py` - Package marker for bundled icons
- `src/linux_speech_flow/icons/freeflow-idle.svg` - Grey circle (#9E9E9E), idle state
- `src/linux_speech_flow/icons/freeflow-recording-1.svg` - Red circle r=6, pulse frame 1
- `src/linux_speech_flow/icons/freeflow-recording-2.svg` - Red circle r=9, pulse frame 2
- `src/linux_speech_flow/icons/freeflow-recording-3.svg` - Red circle r=11, pulse frame 3
- `src/linux_speech_flow/icons/freeflow-processing-1.svg` - Yellow arc at 0deg, spinner frame 1
- `src/linux_speech_flow/icons/freeflow-processing-2.svg` - Yellow arc at 120deg, spinner frame 2
- `src/linux_speech_flow/icons/freeflow-processing-3.svg` - Yellow arc at 240deg, spinner frame 3
- `src/linux_speech_flow/icons/freeflow-error.svg` - Red circle with white X
- `pyproject.toml` - Added trayer==0.1.1 dependency and icons/*.svg to package-data

## Decisions Made

- install_icons() always overwrites (no `if not dest.exists()` guard) so icon updates propagate on app restart
- DBusGMainLoop called at TrayManager.__init__ start per research pitfall 1
- Left-click set to open Settings because trayer's SNI implementation maps right-click to always show menu (cannot redirect right-click to Settings callback)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Icons are auto-installed to XDG hicolor theme at app startup.

## Next Phase Readiness

- TrayManager is ready for Plan 02 to wire to app.py (do_startup, do_activate, pipeline state callbacks)
- install_icons() must be called in App.do_startup() before TrayManager.setup() (documented in RESEARCH.md pitfall 2)
- update_failed_count() ready for TranscriptionPipeline on_failed_count_changed callback wiring

## Self-Check: PASSED

- src/linux_speech_flow/tray.py: FOUND
- src/linux_speech_flow/icons/__init__.py: FOUND
- src/linux_speech_flow/icons/freeflow-idle.svg: FOUND
- src/linux_speech_flow/icons/freeflow-error.svg: FOUND
- Commit e27c9fd: FOUND
- Commit 4491311: FOUND

---
*Phase: 04-system-tray-and-desktop-integration*
*Completed: 2026-02-21*
