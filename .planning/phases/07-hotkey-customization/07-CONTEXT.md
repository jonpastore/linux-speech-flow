# Phase 7: Hotkey Customization - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

User-configurable hotkey bindings in Settings. All 5 current hardcoded bindings become remappable: record toggle (Ctrl+Alt+R), stop recording (ESC), conversation toggle (Ctrl+Alt+C), reprocess failed (Ctrl+Alt+P), feedback mode toggle (Ctrl+Alt+F). Changes take effect immediately without restart. Regular push-to-talk behavior and transcription pipeline are unchanged.

</domain>

<decisions>
## Implementation Decisions

### Hotkey picker UI
- Press-to-capture: each action has a button displaying the current combo (e.g. "Ctrl+Alt+R")
- Clicking the button enters capture mode; label changes to "Press keys..."
- Auto-confirm: as soon as a valid combo (modifier + key) is pressed, capture ends and binding is accepted
- ESC during capture cancels and restores the prior binding
- New binding hot-reloads into HotkeyManager immediately (no restart required)
- Save button persists bindings to config.json

### Which actions are configurable
- All 5 current bindings are configurable: record toggle, stop, conversation toggle, reprocess, feedback toggle
- Stop recording is configurable as a full combo (same press-to-capture as the others — no special bare-key mode)
- New "Hotkeys" section in Settings, placed near the top (after AI Integrations)

### Conflict handling and validation
- On collision: warn and reject — inline error message shown, old binding restored (no silent overwrites)
- Error message format: "[Combo] is already used for [Action]"
- Valid combo requires at least one modifier (Ctrl, Alt, Super, Shift) + one non-modifier key
- Blocked dangerous combos (reject silently with error): Ctrl+Alt+Delete, Ctrl+Alt+F1–F12 (TTY switching), Ctrl+Alt+Left/Right (workspace switching), and equivalents for Linux desktops

### Reset to defaults
- Each row has a per-hotkey reset icon button that restores just that action's default
- "Reset All" button at the bottom of the Hotkeys section restores all 5 defaults at once
- Both per-hotkey and reset-all apply immediately (same hot-reload as capture)

### Claude's Discretion
- Exact appearance of the reset icon (e.g. circular arrow, trash) — standard GTK icon name is fine
- Config key names for each hotkey (e.g. `hotkey_record`, `hotkey_conversation`, etc.)
- How combos are serialized in config.json (string format like "ctrl+alt+r" or structured dict)
- Which exact additional dangerous combos to block beyond the ones named above

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `HotkeyManager` (hotkey.py): currently hardcodes bindings via `_ctrl_held`/`_alt_held` + `_key_letter()`. Needs to read hotkey config at startup and reload on settings change.
- `DEFAULT_CONFIG` (config.py): no hotkey keys yet — new keys needed (e.g. `hotkey_record`, `hotkey_stop`, `hotkey_conversation`, `hotkey_reprocess`, `hotkey_feedback`)
- `save_config()` / `load_config()` (config.py): already handles JSON persistence and default backfill — no new infrastructure needed
- `SettingsWindow` (settings.py): scrollable single-pane, sections use `Gtk.Label` with `title-4` CSS class + rows of label/widget pairs. Hotkeys section follows same pattern.
- Modifier tracking (`_ctrl_held`, `_alt_held`) in `HotkeyManager._on_press`/`_on_release` — reuse or generalize this for parsing captured combos

### Established Patterns
- Settings sections: `Gtk.Label` title with `add_css_class("title-4")`, rows as `Gtk.Box(HORIZONTAL)` with label left, widget right
- Config backfill: new keys added to `DEFAULT_CONFIG` are automatically backfilled by `load_config()` — no migration code needed
- Immediate GTK operations from pynput listener must go via `GLib.idle_add()` (threading contract in `HotkeyManager`)
- `Gtk.Window(modal=True)` is the project pattern; avoid `Gtk.Dialog` (GTK 4.10 deprecated)

### Integration Points
- `HotkeyManager.__init__` → needs to accept or read configurable bindings at construction time
- `app.py` → constructs `HotkeyManager`; needs to pass a reload callback or re-instantiate on settings save
- `settings.py` → Hotkeys section UI writes to config and triggers `HotkeyManager` reload
- `history_window.py:189` → reads `cfg.get('hotkey_record', 'F9')` (stale reference — needs update to use new config key)

</code_context>

<specifics>
## Specific Ideas

- Press-to-capture should feel like GNOME Settings → Keyboard → Shortcuts — that's the reference UX
- Blocked combos: user confirmed Ctrl+Alt+Left and Ctrl+Alt+Right (workspace switching) should be blocked, along with Ctrl+Alt+Delete and Ctrl+Alt+F1–F12

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-hotkey-customization*
*Context gathered: 2026-03-03*
