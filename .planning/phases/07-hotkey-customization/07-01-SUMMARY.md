---
phase: 07-hotkey-customization
plan: "01"
subsystem: hotkey
tags: [pynput, config, hotkey, keybinding, combo-parsing]

requires:
  - phase: 06.1-conversation-status-enhancements
    provides: ConversationStatusWindow, silence accumulation, transcript card UI

provides:
  - parse_combo() and combo_display() module-level helpers in hotkey.py
  - 5 hotkey_* config keys in DEFAULT_CONFIG (Phase 7 additions)
  - HotkeyManager._modifiers_held set replacing _ctrl_held/_alt_held
  - HotkeyManager._bindings dict loaded from config at init and reload
  - HotkeyManager.reload_bindings() for hot-reload from GTK main thread
  - HotkeyManager._matches_binding() for config-driven key dispatch
  - history_window.py shows configured hotkey via combo_display()
  - app.py _on_settings_closed calls reload_bindings()

affects:
  - 07-02 (Settings UI will build hotkey widgets on top of this backend)
  - 07-03 (Test update plan for _ctrl_held/_alt_held -> _modifiers_held migration)

tech-stack:
  added: []
  patterns:
    - "Modifier set pattern: _modifiers_held set + _MODIFIER_MAP instance dict for testable modifier tracking"
    - "Single-char key_id check: len(key_id)==1 routes to _key_letter() before Key enum lookup for mock safety"
    - "Instance _MODIFIER_MAP: built in __init__ so mocked keyboard.Key values are captured correctly in tests"

key-files:
  created: []
  modified:
    - src/linux_speech_flow/config.py
    - src/linux_speech_flow/hotkey.py
    - src/linux_speech_flow/history_window.py
    - src/linux_speech_flow/app.py

key-decisions:
  - "_MODIFIER_MAP built as instance attr in __init__ (not class-level const) so mocked keyboard.Key refs are captured at instantiation time, making tests work without needing a real pynput keyboard"
  - "_matches_binding checks len(key_id)==1 before Key enum lookup to avoid MagicMock always returning truthy on [] access (mock bypass of KeyError)"
  - "record binding checked before stop binding in _on_press so Ctrl+Alt+R while RECORDING calls _stop_recording_hotkey (sets stop_was_hotkey=True) rather than _stop_recording (which does not)"
  - "parse_combo and combo_display are module-level functions (not methods) for use by Plan 02 Settings UI without needing HotkeyManager instance"

requirements-completed: [HOTKEY-01, HOTKEY-02]

duration: 6min
completed: 2026-03-03
---

# Phase 7 Plan 01: Hotkey Backend Refactor Summary

**Config-driven HotkeyManager with parse_combo/combo_display helpers, _modifiers_held set dispatch, and hot-reload via reload_bindings() called from app.py settings close**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-03T06:34:47Z
- **Completed:** 2026-03-03T06:41:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Added 5 hotkey_* keys to DEFAULT_CONFIG with correct Ctrl+Alt defaults
- Implemented parse_combo() and combo_display() with canonical modifier ordering
- Refactored HotkeyManager from hardcoded _ctrl_held/_alt_held booleans to _modifiers_held set + _bindings dict loaded from config
- Added reload_bindings() and _matches_binding() to complete the config-driven dispatch
- Fixed history_window.py stale 'F9' default to use combo_display() with configured hotkey
- Wired app.py _on_settings_closed to call hotkey_manager.reload_bindings()

## Task Commits

1. **Task 1: Add hotkey config defaults and combo parsing helpers** - `9365c1e` (feat)
2. **Task 2: Refactor HotkeyManager to config-driven dispatch with reload_bindings** - `a2b1cc2` (feat)
3. **Task 3: Fix history_window stale hotkey reference and wire app.py reload** - `9dc75b1` (feat)

## Files Created/Modified
- `src/linux_speech_flow/config.py` - Added 5 hotkey_* keys in Phase 7 additions block
- `src/linux_speech_flow/hotkey.py` - parse_combo, combo_display, HOTKEY_DEFAULTS/CONFIG_KEYS/ACTION_LABELS, DANGEROUS_COMBOS, full HotkeyManager refactor
- `src/linux_speech_flow/history_window.py` - combo_display() replaces stale F9 default
- `src/linux_speech_flow/app.py` - reload_bindings() call in _on_settings_closed

## Decisions Made
- `_MODIFIER_MAP` built as instance attribute in `__init__` rather than class-level constant, so the mocked `keyboard.Key` objects during testing are captured at instantiation time
- `_matches_binding` checks `len(key_id) == 1` before attempting `keyboard.Key[key_id]` enum lookup — avoids MagicMock silently returning non-KeyError on `[]` access
- `record` binding checked before `stop` in `_on_press` so Ctrl+Alt+R while recording routes through `_stop_recording_hotkey()` (which sets `_stop_was_hotkey=True`), matching test expectations
- `parse_combo` and `combo_display` are module-level functions (not methods) for Settings UI import without needing a HotkeyManager instance

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _MODIFIER_MAP class-level attribute failed with mocked keyboard**
- **Found during:** Task 2 (HotkeyManager refactor)
- **Issue:** Plan specified `_MODIFIER_MAP` as a class-level constant built at class definition time. When `keyboard` is mocked in tests via `@patch`, the class attribute already holds real `keyboard.Key` objects, not mocked ones. The modifier tracking `key in self._MODIFIER_MAP` never matched, causing 10 test failures.
- **Fix:** Moved `_MODIFIER_MAP` from class body to `__init__`, so it is built with the keyboard module reference active at instantiation time. In tests, that's the mocked keyboard.
- **Files modified:** src/linux_speech_flow/hotkey.py
- **Verification:** Ctrl+Alt+R/C/P/F tests pass; `key in self._MODIFIER_MAP` now works with mocked keyboard.
- **Committed in:** a2b1cc2 (Task 2 commit)

**2. [Rule 1 - Bug] _matches_binding Key enum lookup returned MagicMock (not KeyError) for letter keys**
- **Found during:** Task 2 (HotkeyManager refactor)
- **Issue:** Plan's `_matches_binding` used `keyboard.Key[key_id]` inside try/except KeyError. With real pynput, `keyboard.Key['r']` raises `KeyError` so the fallback `_key_letter()` ran. With mocked keyboard, `mock_kb.Key['r']` returned a MagicMock (no KeyError), so `key == MagicMock` was always False and `_key_letter` was never reached.
- **Fix:** Added `if len(key_id) == 1: return self._key_letter(key) == key_id` before the Key enum lookup. Single-character key_ids are always letter/char keys, not Key enum members.
- **Files modified:** src/linux_speech_flow/hotkey.py
- **Verification:** Ctrl+Alt+R/C/P/F dispatch works in tests; 148/149 tests pass (1 expected failure for _ctrl_held/_alt_held attribute test).
- **Committed in:** a2b1cc2 (Task 2 commit)

**3. [Rule 1 - Bug] _on_press stop-binding logic set stop_was_hotkey=False when record binding matched**
- **Found during:** Task 2 (HotkeyManager refactor)
- **Issue:** Plan's proposed `_on_press` checked 'stop' binding first and called `_stop_recording(False)` which does NOT set `_stop_was_hotkey=True`. When stop==record (default), pressing Ctrl+Alt+R while recording should set `stop_was_hotkey=True` (test assertion).
- **Fix:** Swapped order: check 'record' binding first (routes to `_stop_recording_hotkey` in RECORDING state), then check 'stop' binding for the elif case. This preserves the intent that distinct stop/record bindings work independently while the default same-combo case uses the hotkey stop path.
- **Files modified:** src/linux_speech_flow/hotkey.py
- **Verification:** test_ctrl_alt_r_in_recording_stops_recorder passes with stop_was_hotkey=True.
- **Committed in:** a2b1cc2 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 - bugs in plan's proposed implementation)
**Impact on plan:** All auto-fixes corrected bugs in the plan's proposed code. No scope creep. Functional behavior is identical to what the plan specified.

## Issues Encountered
None beyond the three auto-fixed deviations above. The test `test_on_release_clears_modifier_flags` fails as expected per plan (checks `_ctrl_held`/`_alt_held` attributes which are removed); will be fixed in Plan 03.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend fully operational: parse_combo, combo_display, reload_bindings all work
- Plan 02 (Settings UI) can build hotkey config widgets directly on top of this backend
- Plan 03 must update `test_on_release_clears_modifier_flags` to assert on `_modifiers_held` set instead of `_ctrl_held`/`_alt_held` booleans

---
*Phase: 07-hotkey-customization*
*Completed: 2026-03-03*
