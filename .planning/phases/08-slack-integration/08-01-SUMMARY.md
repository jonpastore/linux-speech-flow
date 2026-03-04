---
phase: 08-slack-integration
plan: 01
subsystem: ui
tags: [slack, slack-sdk, numpy, gtk, settings, hotkey, config]

requires:
  - phase: 07-hotkey-customization
    provides: HotkeyManager with configurable bindings, HOTKEY_DEFAULTS/CONFIG_KEYS/ACTION_LABELS dicts, SettingsWindow hotkey capture UI

provides:
  - slack_manager.py: SlackManager class with verify_token, add_workspace, get_workspaces, remove_workspace, post_message, upload_file
  - config.py: Phase 8 DEFAULT_CONFIG keys — hotkey_huddle, slack_workspaces, slack_huddle_auto_detect, slack_activation_word, slack_confidence_threshold
  - hotkey.py: huddle action in all three HOTKEY_* dicts, _STATE_HUDDLE, on_huddle_start/stop callbacks, _huddle_start/_huddle_stop methods, public reset_to_idle()
  - settings.py: Integrations section with Slack workspace connection UI and huddle settings
  - pyproject.toml: slack-sdk>=3.40.1 and numpy>=1.24 declared

affects: [08-02, 08-03, 08-04]

tech-stack:
  added: [slack-sdk>=3.40.1, numpy>=1.24]
  patterns: [_path kwarg injection for config in SlackManager, dict() copy of DEFAULT_CONFIG mutable values, GObject __gsignals__ for custom signals on Gtk.Window subclass, background thread verify with GLib.idle_add result dispatch]

key-files:
  created:
    - src/linux_speech_flow/slack_manager.py
    - tests/test_slack_manager.py
  modified:
    - pyproject.toml
    - src/linux_speech_flow/config.py
    - src/linux_speech_flow/hotkey.py
    - src/linux_speech_flow/settings.py

key-decisions:
  - "SlackManager uses _path kwarg (same pattern as load_config/save_config) for test injection — no monkeypatching needed"
  - "dict() shallow copy of slack_workspaces from load_config to prevent mutating DEFAULT_CONFIG mutable dict (shallow copy bug)"
  - "AddWorkspaceDialog emits workspace-added GObject signal on successful connect so SettingsWindow can refresh the list"
  - "files_upload_v2 used (not deprecated files.upload sunset Nov 2025)"
  - "verify_token returns (bool, str) tuple: ok flag + error message for UI display"
  - "Workspace add/disconnect save immediately (like API key saves) without waiting for Settings Save button"

patterns-established:
  - "SlackManager._path injection pattern: all config-touching methods accept keyword-only _path=CONFIG_PATH for test isolation"
  - "dict() copy pattern for mutable DEFAULT_CONFIG values to prevent cross-test contamination"

requirements-completed: [SLACK-01]

duration: 7min
completed: 2026-03-04
---

# Phase 8 Plan 01: Slack Integration Foundation Summary

**slack-sdk foundation with SlackManager API layer, Ctrl+Alt+H huddle hotkey, guided workspace token setup UI in Settings Integrations section**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-04T03:38:07Z
- **Completed:** 2026-03-04T03:45:11Z
- **Tasks:** 3 (Task 2 had TDD RED + GREEN commits)
- **Files modified:** 6

## Accomplishments

- SlackManager class with verify_token, workspace CRUD, post_message, upload_file (using files_upload_v2)
- Ctrl+Alt+H huddle hotkey added to HotkeyManager with _STATE_HUDDLE, callbacks, and reset_to_idle()
- Settings Integrations section with guided 4-step Slack app creation walkthrough and AddWorkspaceDialog
- 14 new tests covering all SlackManager paths (happy, error, persistence)

## Task Commits

1. **Task 1: slack-sdk+numpy deps, Slack config defaults, huddle hotkey** - `756fbd0` (feat)
2. **Task 2 RED: failing tests for SlackManager** - `391b7d0` (test)
3. **Task 2 GREEN: implement SlackManager** - `5252815` (feat)
4. **Task 3: Integrations section in SettingsWindow** - `50a804c` (feat)

## Files Created/Modified

- `src/linux_speech_flow/slack_manager.py` - SlackManager class: verify_token, add/get/remove_workspace, post_message, upload_file
- `tests/test_slack_manager.py` - 14 tests covering all SlackManager methods
- `pyproject.toml` - Added slack-sdk>=3.40.1 and numpy>=1.24 dependencies
- `src/linux_speech_flow/config.py` - Phase 8 DEFAULT_CONFIG keys: hotkey_huddle, slack_workspaces, slack_huddle_auto_detect, slack_activation_word, slack_confidence_threshold
- `src/linux_speech_flow/hotkey.py` - huddle in HOTKEY_DEFAULTS/CONFIG_KEYS/ACTION_LABELS, _STATE_HUDDLE, on_huddle_start/stop params, _huddle_start/_stop methods, reset_to_idle()
- `src/linux_speech_flow/settings.py` - Integrations section, AddWorkspaceDialog class, dirty tracking + save for Slack config keys

## Decisions Made

- SlackManager uses `_path` kwarg injection (same pattern as `load_config`/`save_config`) for test isolation — no monkeypatching needed
- `dict()` shallow copy of `slack_workspaces` when reading from `load_config()` to prevent mutating `DEFAULT_CONFIG`'s mutable dict instance (discovered during TDD GREEN)
- `AddWorkspaceDialog` emits `workspace-added` GObject signal on successful connect so `SettingsWindow` can refresh the workspace list
- `files_upload_v2` used in upload_file (not deprecated `files.upload` which was sunset Nov 2025)
- `verify_token` returns `(bool, str)` tuple — ok flag plus error message string for UI display
- Workspace add/disconnect save immediately (like API key saves) without waiting for Settings Save button

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed shallow copy mutation of DEFAULT_CONFIG slack_workspaces**
- **Found during:** Task 2 GREEN (SlackManager implementation + test run)
- **Issue:** `load_config()` does `config = dict(DEFAULT_CONFIG)` which is a shallow copy. `config["slack_workspaces"]` pointed to the same dict object as `DEFAULT_CONFIG["slack_workspaces"]`. Mutating it in `add_workspace` mutated the DEFAULT_CONFIG, causing cross-test contamination.
- **Fix:** Changed `workspaces = config.get("slack_workspaces", {})` to `workspaces = dict(config.get("slack_workspaces", {}))` in both `add_workspace` and `remove_workspace`.
- **Files modified:** src/linux_speech_flow/slack_manager.py
- **Verification:** `test_get_workspaces_empty_returns_dict` now passes in all test orderings (14/14 pass)
- **Committed in:** `5252815` (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug fix)
**Impact on plan:** Essential correctness fix — mutating DEFAULT_CONFIG would cause flaky tests and production bugs where slack_workspaces accumulates stale data across config loads. No scope creep.

## Issues Encountered

- venv uses Python 3.10 which lacks `tomllib` stdlib module (added in 3.11). Used string search on pyproject.toml content instead for verification.
- slack-sdk was not yet installed in .venv — installed via `pip install slack-sdk>=3.40.1` before TDD.

## Next Phase Readiness

- SlackManager fully tested and ready for Phase 08-02 (huddle audio recording + upload)
- Ctrl+Alt+H hotkey wired up but on_huddle_start/stop callbacks not yet connected in app.py — Phase 08-02 task
- Workspace connection UI complete; users can add workspaces before audio features are built

---
*Phase: 08-slack-integration*
*Completed: 2026-03-04*
