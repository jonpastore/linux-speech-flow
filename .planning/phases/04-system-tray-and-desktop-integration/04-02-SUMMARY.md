---
phase: 04-system-tray-and-desktop-integration
plan: 02
subsystem: ui
tags: [gtk4, system-tray, trayer, dbus, xdg-autostart, headless, desktop-notification]

requires:
  - phase: 04-system-tray-and-desktop-integration/04-01
    provides: TrayManager class with set_state(), update_failed_count(), install_icons() ready for wiring

provides:
  - App runs headless (no placeholder window) via self.hold() when setup_complete
  - TrayManager wired to all 4 pipeline state transitions (recording/processing/idle/error)
  - HotkeyManager fires on_recording_start callback on GTK thread in _start_recording()
  - TranscriptionPipeline fires on_failed_count_changed via GLib.idle_add after every failed/ directory change
  - Desktop notifications sent with 'FreeFlow Error' title on recording error and pipeline error
  - XDG autostart .desktop file at ~/.config/autostart/freeflow.desktop using sys.executable

affects:
  - 04-03 (autostart .desktop file already installed; phase 3 may add user-facing config)

tech-stack:
  added: []
  patterns:
    - "Headless GTK application: self.hold() replaces placeholder window when setup_complete"
    - "Error state auto-clears: next F9 press calls set_state('recording'), displacing 'error'"
    - "sys.executable used in autostart Exec= path — always the venv Python regardless of install location"
    - "on_failed_count_changed returns False from GLib.idle_add: single-fire, no re-invocation"

key-files:
  created: []
  modified:
    - src/linux_speech_flow/hotkey.py
    - src/linux_speech_flow/transcription.py
    - src/linux_speech_flow/app.py

key-decisions:
  - "sys.executable used for autostart Exec= path (simpler and always resolves to running venv Python)"
  - "on_recording_start callback position: fires after state=RECORDING, before config load and recorder start (tray shows recording before audio begins)"
  - "_notify_failed_count() called after try/except in both os.unlink paths and inside _save_failed_wav() try block — fresh glob always reflects actual dir state"

patterns-established:
  - "GLib.idle_add(self._on_failed_count_changed, count): passes count as arg, callback returns False (single-fire)"
  - "Tray state wiring: all 4 states wired in App callbacks — recording (start), processing (complete), idle (paste done), error (error handlers)"

requirements-completed: [TRAY-03, TRAY-04]

duration: 2min
completed: 2026-02-21
---

# Phase 04 Plan 02: Headless App with TrayManager Wiring and XDG Autostart

**App converted to headless mode: TrayManager wired for all 4 state transitions, HotkeyManager and TranscriptionPipeline callbacks added, and ~/.config/autostart/freeflow.desktop installed using sys.executable.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T11:15:38Z
- **Completed:** 2026-02-21T11:17:36Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- HotkeyManager now fires `on_recording_start` callback immediately on `_start_recording()` (GTK main thread), enabling tray to show 'recording' state before audio begins
- TranscriptionPipeline adds `_get_failed_count()` / `_notify_failed_count()` helpers; callback fires on every failed/ directory change (WAV in or out)
- App.py rewritten: placeholder window removed, `self.hold()` used for headless operation, TrayManager wired with all 4 state callbacks, `_install_autostart()` writes valid XDG .desktop file

## Task Commits

1. **Task 1: Add on_recording_start to HotkeyManager and on_failed_count_changed to TranscriptionPipeline** - `07f33af` (feat)
2. **Task 2: Convert app.py to headless mode with TrayManager wiring and XDG autostart** - `67bfdd3` (feat)

## Files Created/Modified

- `src/linux_speech_flow/hotkey.py` - Added `on_recording_start` kwarg and `_on_recording_start_cb()` call in `_start_recording()`
- `src/linux_speech_flow/transcription.py` - Added `on_failed_count_changed` kwarg, `_get_failed_count()`, `_notify_failed_count()`, and 3 call sites
- `src/linux_speech_flow/app.py` - Headless mode, TrayManager wiring, autostart install, removed placeholder window

## Decisions Made

- `sys.executable` used for autostart `Exec=` path — simpler than reconstructing venv path from `__file__` and always resolves to the running Python
- `_notify_failed_count()` called after the try/except block for `os.unlink` (not inside) in `_process()` — ensures count fires even if unlink raises OSError, since the WAV may still have been consumed
- `on_recording_start` fires after `self._state = self._STATE_RECORDING` but before config load and AudioRecorder start — tray shows 'recording' immediately on F9 press

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - XDG autostart .desktop file is written automatically at app startup. No user action needed to enable autostart.

## Next Phase Readiness

- All Phase 4 observable behaviors are wired: tray state changes with every pipeline event, failed count updates live, menu actions work, autostart is installed
- Phase 4 Plan 03 (if it exists) can address any remaining integration verification or packaging concerns
- The app can now be launched end-to-end with full tray integration

## Self-Check: PASSED

- src/linux_speech_flow/hotkey.py: FOUND
- src/linux_speech_flow/transcription.py: FOUND
- src/linux_speech_flow/app.py: FOUND
- Commit 07f33af: FOUND
- Commit 67bfdd3: FOUND

---
*Phase: 04-system-tray-and-desktop-integration*
*Completed: 2026-02-21*
