---
phase: 07-hotkey-customization
plan: "04"
subsystem: ui
tags: [hotkeys, pynput, gtk, settings, config]

requires:
  - phase: 07-01
    provides: "HotkeyManager with _modifiers_held, parse_combo, combo_display, HOTKEY_DEFAULTS, HOTKEY_CONFIG_KEYS"
  - phase: 07-02
    provides: "SettingsWindow Hotkeys section with press-to-capture state machine"
  - phase: 07-03
    provides: "Test suite for hotkey module and settings capture state machine"
provides:
  - "Reviewed and corrected hotkey.py with complete threading contract documentation"
  - "Verified settings.py, history_window.py, app.py all pass review checklist"
  - "178 tests pass, 0 failures — Phase 7 feature confirmed complete and correct"
affects: [phase-08-slack-integration, phase-09-packaging]

tech-stack:
  added: []
  patterns:
    - "Threading contract: _bindings read from pynput thread, written only from GTK main thread — GIL + GTK single-thread rule provides ordering"

key-files:
  created: []
  modified:
    - src/linux_speech_flow/hotkey.py

key-decisions:
  - "Threading contract docstring updated: _bindings dict access pattern documented (pynput read, GTK write)"
  - "_on_press checks record before stop intentionally: Ctrl+Alt+R while RECORDING hits record branch RECORDING case, firing _stop_recording_hotkey (stop_was_hotkey=True) — correct per 07-01 decision"
  - "Gtk.MessageDialog in _show_unsaved_dialog is pre-existing (pre-Phase-7), out of scope for this review"
  - "settings.py uses HOTKEY_CONFIG_KEYS dict (no magic strings) — verification script literal check was flawed, code is correct"

patterns-established:
  - "Review plan: verify against checklist, cross-reference STATE.md decisions when checklist conflicts with existing code"

requirements-completed: [HOTKEY-01, HOTKEY-02]

duration: 8min
completed: 2026-03-03
---

# Phase 7 Plan 04: Code Review Summary

**Phase 7 hotkey customization review: threading contract documented, all 5 files pass full checklist, 178 tests pass**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-03T00:00:00Z
- **Completed:** 2026-03-03T00:08:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Reviewed all 5 Phase 7 modified files (hotkey.py, config.py, settings.py, history_window.py, app.py) against the full review checklist
- Found and fixed the only real issue: threading contract docstring in HotkeyManager was missing documentation about `_bindings` dict thread access semantics
- Confirmed all other checklist items pass: canonical combo ordering, DANGEROUS_COMBOS (15 entries, all required present), modifier tracking, no stale `_ctrl_held`/`_alt_held` references, settings capture state machine, history_window using combo_display with hotkey_record config key, app.py passing hotkey_manager to SettingsWindow and calling reload_bindings on close

## Task Commits

1. **Task 1: Review hotkey.py and config.py** - `9ca91d9` (feat: threading contract docstring update)
2. **Task 2: Review settings.py, history_window.py, app.py** - no code changes needed (all checklist items confirmed correct)

## Files Created/Modified

- `src/linux_speech_flow/hotkey.py` - Updated HotkeyManager class docstring threading contract section to document `_bindings` dict thread access pattern

## Review Findings

### hotkey.py

| Item | Status | Notes |
|------|--------|-------|
| parse_combo, combo_display, HOTKEY_DEFAULTS, HOTKEY_CONFIG_KEYS, HOTKEY_ACTION_LABELS, DANGEROUS_COMBOS all present as module-level exports | PASS | |
| `_MODIFIER_NAMES` and `_MODIFIER_ORDER` defined before any function using them | PASS | Lines 14-15 |
| combo_display enforces canonical modifier order (ctrl → alt → shift → super) | PASS | combo_display('alt+ctrl+r') == 'Ctrl+Alt+R' verified |
| parse_combo handles empty string: returns (frozenset(), '') | PASS | |
| DANGEROUS_COMBOS: all 15 expected entries present (14 required + ctrl+alt+f6 as extra) | PASS | Count: 15 |
| `_MODIFIER_MAP` is instance attribute (not class-level) covering ctrl/alt/shift/super + _l/_r variants + alt_gr | PASS | Initialized in __init__ |
| __init__ initializes _modifiers_held as set(), _bindings as {} | PASS | |
| No _ctrl_held or _alt_held in HotkeyManager source | PASS | |
| _reload_bindings_from_config uses HOTKEY_DEFAULTS and HOTKEY_CONFIG_KEYS (no hardcoded strings) | PASS | |
| _matches_binding handles keyboard.Key members and char keys; try/except KeyError for unknown key_id | PASS | |
| _on_press checks _MODIFIER_MAP FIRST before _started guard | PASS | Prevents stuck modifier on startup |
| _on_press record before stop (record handles RECORDING→stop via _stop_recording_hotkey with stop_was_hotkey=True) | PASS | Correct per 07-01 decision; checklist item had reversed wording |
| _on_release uses discard not remove | PASS | Line 228 |
| reload_bindings() public and documented in class docstring | PASS | |
| apply_binding_override(action, combo_str) present | PASS | |
| Threading contract updated to mention _bindings thread access | **FIXED** | Was missing; added 4-line explanation |

### config.py

| Item | Status | Notes |
|------|--------|-------|
| All 5 hotkey_* keys in DEFAULT_CONFIG with correct defaults | PASS | Lines 117-121 |
| Phase 7 additions comment block present and consistent with prior phase comments | PASS | "# Phase 7 additions" at line 116 |
| No stale keys (conv_hotkey_start, conv_hotkey_feedback) | PASS | Removed in commit 6ff4ff6 |

### settings.py

| Item | Status | Notes |
|------|--------|-------|
| hotkey_manager optional parameter in __init__ | PASS | Default None |
| Hotkeys section after Gemini, before Vocabulary | PASS | Position verified |
| Section title uses title-4 CSS class and set_xalign(0) | PASS | |
| Each row: Gtk.Box(HORIZONTAL, spacing=8) with label (hexpand+xalign=0), capture button, reset icon button | PASS | |
| Reset icon uses view-refresh-symbolic with tooltip showing default | PASS | |
| _on_key_pressed routes to _handle_capture_key only when _capture_action is truthy | PASS | |
| _handle_capture_key returns True in all code paths | PASS | 5 return True paths |
| _GTK_MODIFIER_KEYSYMS lazy init via try/except NameError | PASS | |
| set_focus(None) called in _on_capture_click | PASS | |
| _cancel_capture restores label using combo_display(prev) | PASS | |
| _accept_capture validates dangerous combos first, then conflicts | PASS | |
| _apply_binding calls apply_binding_override (not reload_bindings) | PASS | |
| _apply_binding calls _mark_dirty() | PASS | |
| _on_save writes all 5 hotkey values via HOTKEY_CONFIG_KEYS | PASS | Uses dict iteration |
| No new Gtk.Dialog in Phase 7 code | PASS | Pre-existing Gtk.MessageDialog in _show_unsaved_dialog is out of scope |
| No magic string literals for action names in new code | PASS | All action strings via HOTKEY_CONFIG_KEYS/HOTKEY_DEFAULTS/HOTKEY_ACTION_LABELS |

### history_window.py

| Item | Status | Notes |
|------|--------|-------|
| combo_display(hotkey_combo) called at line 191 | PASS | |
| combo_display imported locally inside if-block | PASS | Line 189 |
| Config key is 'hotkey_record' with default 'ctrl+alt+r' | PASS | |
| No 'F9' reference anywhere in file | PASS | |

### app.py

| Item | Status | Notes |
|------|--------|-------|
| _on_settings_closed calls self._hotkey_manager.reload_bindings() inside if guard | PASS | Lines 113-117 |
| _on_open_settings passes hotkey_manager=self._hotkey_manager | PASS | Line 109 |
| Only one SettingsWindow creation in app.py | PASS | |

### Cross-cutting style

| Item | Status |
|------|--------|
| No new code comments unless explaining non-obvious decisions | PASS |
| No emojis in new code or comments | PASS |
| New method names follow snake_case | PASS |
| No magic string literals for action names outside the three dicts | PASS |

**Final test count: 178 passed, 0 failures, 0 errors**

## Decisions Made

- Threading contract docstring fix is necessary: `_bindings` is accessed from the pynput daemon thread in `_on_press`/`_matches_binding` but written from GTK main thread in `reload_bindings()` and `apply_binding_override()`. The GIL provides atomic reads/writes for dict assignment in CPython, and the GTK single-thread rule ensures writes are serialized. Documentation was missing; added 4-line explanation.
- The plan's checklist item "stop before record in _on_press" conflicts with the Phase 07-01 STATE.md decision. The existing code (record before stop) is intentionally correct: when both default to ctrl+alt+r and state is RECORDING, the record branch's `elif self._state == self._STATE_RECORDING` path calls `_stop_recording_hotkey` preserving `stop_was_hotkey=True`. No change made.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Threading contract docstring missing _bindings access documentation**
- **Found during:** Task 1 (Review hotkey.py and config.py)
- **Issue:** HotkeyManager docstring Threading contract section did not mention that `_bindings` is read from the pynput thread but written only from the GTK main thread via `reload_bindings()` or `apply_binding_override()`. This is a subtle threading contract that future maintainers need to understand.
- **Fix:** Added 4-line paragraph to the Threading contract docstring explaining the access pattern and why no explicit lock is needed (GIL + GTK single-thread rule).
- **Files modified:** src/linux_speech_flow/hotkey.py
- **Verification:** All 60 hotkey/config tests still pass; docstring updated confirmed
- **Committed in:** 9ca91d9

---

**Total deviations:** 1 auto-fixed (documentation correctness)
**Impact on plan:** Minor docstring update for threading contract completeness. No behavior changes. No scope creep.

## Issues Encountered

None — all Phase 7 code was functionally correct. The review confirmed clean implementation of the configurable hotkeys feature.

## Next Phase Readiness

Phase 7 complete. All 5 modified files reviewed and verified:
- Configurable hotkeys in Settings with press-to-capture GNOME-style UI
- Hot-reload without restart via apply_binding_override + reload_bindings
- Conflict detection and dangerous combo blocking
- Per-hotkey and Reset All buttons
- history_window showing correct binding from config
- 178 tests pass

Ready for Phase 8 (Slack Integration).

---
*Phase: 07-hotkey-customization*
*Completed: 2026-03-03*
