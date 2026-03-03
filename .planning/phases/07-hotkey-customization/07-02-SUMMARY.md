---
phase: 07-hotkey-customization
plan: "02"
subsystem: ui
tags: [gtk, hotkey, settings, capture-state-machine, keybinding]

requires:
  - phase: 07-hotkey-customization
    plan: "01"
    provides: parse_combo, combo_display, HOTKEY_DEFAULTS, HOTKEY_CONFIG_KEYS, HOTKEY_ACTION_LABELS, DANGEROUS_COMBOS, HotkeyManager.reload_bindings

provides:
  - Hotkeys section in SettingsWindow after AI Integrations with 5 configurable action rows
  - Capture state machine in SettingsWindow (GTK EventControllerKey-based press-to-capture)
  - _handle_capture_key, _accept_capture, _cancel_capture, _apply_binding methods in SettingsWindow
  - _make_hotkey_row helper for label + capture button + reset icon rows
  - Per-hotkey reset and Reset All Hotkeys to Defaults buttons
  - HotkeyManager.apply_binding_override() for pre-save in-memory hot-reload
  - _on_save persists all hotkey_* config keys to config.json
  - app.py passes hotkey_manager to SettingsWindow for immediate hot-reload

affects:
  - 07-03 (test update plan — SettingsWindow hotkey tests TBD)

tech-stack:
  added: []
  patterns:
    - "Capture state machine: _capture_action sentinel (None = idle, action_str = capturing); set_focus(None) releases button focus so window EventControllerKey receives keys"
    - "Lazy _GTK_MODIFIER_KEYSYMS global: initialized via try/except NameError inside _handle_capture_key to avoid gi import at module level"
    - "apply_binding_override: direct _bindings dict update in HotkeyManager bypasses config read for pre-save hot-reload; reload_bindings() still used on settings close for full config sync"

key-files:
  created: []
  modified:
    - src/linux_speech_flow/settings.py
    - src/linux_speech_flow/hotkey.py
    - src/linux_speech_flow/app.py

key-decisions:
  - "set_focus(None) called in _on_capture_click to release GTK focus from the clicked button, ensuring window-level EventControllerKey receives subsequent key events rather than the button widget"
  - "apply_binding_override updates _bindings in-memory directly (not via config) enabling immediate effect before Save; reload_bindings() called on settings close remains the full config-sync path"
  - "Lazy _GTK_MODIFIER_KEYSYMS initialization via try/except NameError (not module-level constant) avoids importing Gdk before gi.require_version is guaranteed to have been called"
  - "Canonical modifier order ['ctrl','alt','shift','super'] enforced in _handle_capture_key combo_str construction so captured strings match DANGEROUS_COMBOS frozenset exactly"

requirements-completed: [HOTKEY-01, HOTKEY-02]

duration: 4min
completed: 2026-03-03
---

# Phase 7 Plan 02: Hotkeys Settings UI Summary

**GNOME-style press-to-capture hotkey section in SettingsWindow: 5 configurable action rows with conflict/danger detection, per-hotkey and Reset All buttons, and immediate in-memory hot-reload via apply_binding_override()**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-03T23:44:26Z
- **Completed:** 2026-03-03T23:48:00Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- Added Hotkeys section to SettingsWindow between AI Integrations and Vocabulary with 5 action rows
- Implemented full capture state machine: click to enter capture mode, press combo to accept, ESC to cancel, conflict and dangerous combo detection with inline error messages
- Added `apply_binding_override()` to HotkeyManager so new bindings take effect immediately without requiring Save or app restart
- Connected app.py to pass hotkey_manager reference into SettingsWindow for live hot-reload

## Task Commits

1. **Task 1: Add Hotkeys section to SettingsWindow with capture state machine** - `4e9d66e` (feat)

## Files Created/Modified
- `src/linux_speech_flow/settings.py` - Added hotkey_manager param, Hotkeys section UI, capture state machine methods, save integration
- `src/linux_speech_flow/hotkey.py` - Added apply_binding_override() to HotkeyManager
- `src/linux_speech_flow/app.py` - Updated _on_open_settings to pass hotkey_manager

## Decisions Made
- `set_focus(None)` clears GTK focus from the capture button so the window-level EventControllerKey receives key events (buttons consume keyboard input by default)
- `apply_binding_override()` updates the in-memory `_bindings` dict directly for pre-save hot-reload; `reload_bindings()` remains the full config-sync path called when settings close
- Lazy `_GTK_MODIFIER_KEYSYMS` global initialization via `try/except NameError` inside `_handle_capture_key` prevents Gdk import at module load time before `gi.require_version` guarantee
- Canonical modifier order `['ctrl','alt','shift','super']` enforced during combo_str construction in `_handle_capture_key` to ensure captured strings match DANGEROUS_COMBOS exactly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Settings UI capture state machine fully operational
- Plan 03 can add tests for SettingsWindow hotkey UI and update stale test_on_release_clears_modifier_flags
- Plan 04 (help window update) can reference configured hotkeys via combo_display()

---
*Phase: 07-hotkey-customization*
*Completed: 2026-03-03*
