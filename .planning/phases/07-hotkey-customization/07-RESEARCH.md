# Phase 7: Hotkey Customization - Research

**Researched:** 2026-03-03
**Domain:** GTK4 key capture UI + pynput configurable binding dispatch
**Confidence:** HIGH

## Summary

Phase 7 replaces HotkeyManager's five hardcoded Ctrl+Alt bindings with user-configurable combos stored in config.json. The UI model is press-to-capture: clicking a button in the new "Hotkeys" Settings section enters capture mode, the next valid key combination is auto-accepted, ESC cancels. New bindings hot-reload into HotkeyManager immediately — no restart required.

The codebase is already well-prepared for this work. `load_config()` / `save_config()` handle JSON persistence with automatic default backfill — adding five new keys to `DEFAULT_CONFIG` is sufficient. `HotkeyManager._on_press` currently hardcodes the binding logic but is straightforward to refactor: replace the five hardcoded comparisons with a dict lookup against parsed config values. The Settings window follows a clear, repetitive section pattern that is easy to extend.

The only non-trivial problem is key capture inside a GTK window. GTK4 `EventControllerKey` on a modal-like button works but has a limitation: the window must have focus. The capture approach used by GNOME Settings (the reference UX per CONTEXT.md) uses a dedicated capture button that grabs the keyboard — implemented in GTK4 via `Gtk.EventControllerKey` on the window, enabled only when capture mode is active. This avoids requiring a separate modal dialog.

**Primary recommendation:** Implement capture via `Gtk.EventControllerKey` on the SettingsWindow itself, gated by a per-row `_capturing` flag. When a button is clicked, set the flag and connect a one-shot `key-pressed` handler that parses and validates the combo, then removes itself.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Hotkey picker UI:**
- Press-to-capture: each action has a button displaying the current combo (e.g. "Ctrl+Alt+R")
- Clicking the button enters capture mode; label changes to "Press keys..."
- Auto-confirm: as soon as a valid combo (modifier + key) is pressed, capture ends and binding is accepted
- ESC during capture cancels and restores the prior binding
- New binding hot-reloads into HotkeyManager immediately (no restart required)
- Save button persists bindings to config.json

**Which actions are configurable:**
- All 5 current bindings are configurable: record toggle, stop, conversation toggle, reprocess, feedback toggle
- Stop recording is configurable as a full combo (same press-to-capture as the others — no special bare-key mode)
- New "Hotkeys" section in Settings, placed near the top (after AI Integrations)

**Conflict handling and validation:**
- On collision: warn and reject — inline error message shown, old binding restored (no silent overwrites)
- Error message format: "[Combo] is already used for [Action]"
- Valid combo requires at least one modifier (Ctrl, Alt, Super, Shift) + one non-modifier key
- Blocked dangerous combos (reject silently with error): Ctrl+Alt+Delete, Ctrl+Alt+F1–F12 (TTY switching), Ctrl+Alt+Left/Right (workspace switching)

**Reset to defaults:**
- Each row has a per-hotkey reset icon button that restores just that action's default
- "Reset All" button at the bottom of the Hotkeys section restores all 5 defaults at once
- Both per-hotkey and reset-all apply immediately (same hot-reload as capture)

### Claude's Discretion
- Exact appearance of the reset icon (e.g. circular arrow, trash) — standard GTK icon name is fine
- Config key names for each hotkey (e.g. `hotkey_record`, `hotkey_conversation`, etc.)
- How combos are serialized in config.json (string format like "ctrl+alt+r" or structured dict)
- Which exact additional dangerous combos to block beyond the ones named above

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HOTKEY-01 | Settings includes a hotkey picker for each action (record, stop, conversation mode, replay failed) | GTK4 EventControllerKey capture pattern, press-to-capture button UI in SettingsWindow |
| HOTKEY-02 | User can set key combinations and changes take effect without restart | HotkeyManager reload_bindings() method, hot-reload via callback from SettingsWindow._on_save |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pynput | already in project | Key event listening + modifier detection | Already powers all hotkey detection |
| GTK4 / PyGObject | already in project | Settings UI + key capture widget | Already the UI framework |
| gi.repository.Gdk | already in project | Key constant lookup (Gdk.KEY_*) | Same display layer as SettingsWindow |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| GLib.idle_add | already in project | Thread-safe GTK dispatch | Required when calling GTK from pynput listener thread |

No new dependencies required.

**Installation:**
```bash
# No new packages — all requirements already installed
```

## Architecture Patterns

### Recommended Project Structure
```
src/linux_speech_flow/
├── hotkey.py         # HotkeyManager: add reload_bindings() + config-driven _on_press
├── config.py         # DEFAULT_CONFIG: add 5 hotkey keys
├── settings.py       # SettingsWindow: add Hotkeys section with capture buttons
└── app.py            # Pass reload callback to SettingsWindow or re-bind on settings close
```

### Pattern 1: Config Key Serialization

**What:** Store hotkey combos as pipe-delimited modifier+key strings in config.json.
**When to use:** Simple, human-readable, round-trips cleanly through JSON, easy to validate.
**Example:**
```python
# DEFAULT_CONFIG additions in config.py
"hotkey_record":       "ctrl+alt+r",
"hotkey_stop":         "ctrl+alt+r",   # same as record (toggle)
"hotkey_conversation": "ctrl+alt+c",
"hotkey_reprocess":    "ctrl+alt+p",
"hotkey_feedback":     "ctrl+alt+f",
```

Serialization format: lowercase modifier names joined with `+`, then `+`, then key identifier.
- For letter keys: the letter (`r`, `c`, `p`, `f`)
- For special keys: pynput Key name (`esc`, `f5`, `delete`, `left`)
- Modifier names: `ctrl`, `alt`, `shift`, `super` (maps to pynput Key.cmd / Key.cmd_r)

```python
def parse_combo(combo_str: str) -> tuple[frozenset[str], str]:
    """Parse 'ctrl+alt+r' -> ({'ctrl', 'alt'}, 'r')"""
    parts = combo_str.lower().split('+')
    MODIFIER_NAMES = {'ctrl', 'alt', 'shift', 'super'}
    modifiers = frozenset(p for p in parts if p in MODIFIER_NAMES)
    key_parts = [p for p in parts if p not in MODIFIER_NAMES]
    return modifiers, key_parts[0] if key_parts else ''

def combo_display(combo_str: str) -> str:
    """'ctrl+alt+r' -> 'Ctrl+Alt+R'"""
    DISPLAY = {'ctrl': 'Ctrl', 'alt': 'Alt', 'shift': 'Shift', 'super': 'Super'}
    parts = combo_str.split('+')
    return '+'.join(DISPLAY.get(p, p.upper()) for p in parts)
```

### Pattern 2: HotkeyManager Config-Driven Dispatch

**What:** Replace hardcoded modifier+letter checks with a parsed binding dict loaded at construction and on `reload_bindings()`.
**When to use:** Whenever settings change — called from app.py after SettingsWindow saves.

```python
# In HotkeyManager.__init__:
self._bindings = {}   # action -> (frozenset[modifier_names], key_identifier)
self._reload_bindings_from_config()

def reload_bindings(self) -> None:
    """Hot-reload bindings from config. Called after settings save."""
    self._reload_bindings_from_config()

def _reload_bindings_from_config(self) -> None:
    config = load_config()
    self._bindings = {
        'record':       parse_combo(config.get('hotkey_record', 'ctrl+alt+r')),
        'stop':         parse_combo(config.get('hotkey_stop', 'ctrl+alt+r')),
        'conversation': parse_combo(config.get('hotkey_conversation', 'ctrl+alt+c')),
        'reprocess':    parse_combo(config.get('hotkey_reprocess', 'ctrl+alt+p')),
        'feedback':     parse_combo(config.get('hotkey_feedback', 'ctrl+alt+f')),
    }
```

**Modifier detection generalization:** The existing `_ctrl_held` / `_alt_held` booleans need to expand to track all four modifiers:

```python
# New modifier state tracking
self._modifiers_held: set[str] = set()   # 'ctrl', 'alt', 'shift', 'super'

# In _on_press:
MODIFIER_MAP = {
    keyboard.Key.ctrl:   'ctrl', keyboard.Key.ctrl_r: 'ctrl',
    keyboard.Key.alt:    'alt',  keyboard.Key.alt_r:  'alt',
    keyboard.Key.alt_gr: 'alt',
    keyboard.Key.shift:  'shift', keyboard.Key.shift_r: 'shift',
    keyboard.Key.cmd:    'super', keyboard.Key.cmd_r:   'super',
}
if key in MODIFIER_MAP:
    self._modifiers_held.add(MODIFIER_MAP[key])
    return

# In _on_release:
if key in MODIFIER_MAP:
    self._modifiers_held.discard(MODIFIER_MAP[key])
    return
```

**Key matching in _on_press:**
```python
def _matches_binding(self, key, binding: tuple[frozenset, str]) -> bool:
    mods, key_id = binding
    if self._modifiers_held != mods:
        return False
    # Special key (pynput.Key enum member)
    try:
        return key == keyboard.Key[key_id]
    except KeyError:
        pass
    # Letter/char key
    return self._key_letter(key) == key_id
```

### Pattern 3: GTK4 Key Capture in SettingsWindow

**What:** Press-to-capture using an `EventControllerKey` on the SettingsWindow itself. A `_capture_action` flag tracks which action is being captured. The existing per-window `key_ctrl` (used for ESC) needs to be upgraded to handle capture mode.

**Threading note:** SettingsWindow key events fire on the GTK main thread (not pynput's thread) — no `GLib.idle_add` needed for UI updates within capture.

```python
# Per-row capture button setup
def _make_hotkey_row(self, label: str, action: str, combo_str: str) -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    lbl = Gtk.Label(label=label)
    lbl.set_hexpand(True)
    lbl.set_xalign(0)
    btn = Gtk.Button(label=combo_display(combo_str))
    btn.connect("clicked", self._on_capture_click, action)
    reset_btn = Gtk.Button()
    reset_btn.set_icon_name("view-refresh-symbolic")
    reset_btn.set_tooltip_text(f"Reset to default")
    reset_btn.connect("clicked", self._on_reset_hotkey, action)
    row.append(lbl)
    row.append(btn)
    row.append(reset_btn)
    return row

# Capture state
self._capture_action: str | None = None
self._capture_buttons: dict[str, Gtk.Button] = {}
self._capture_prev_combo: str | None = None

# The existing key_ctrl is already connected to _on_key_pressed.
# Extend _on_key_pressed to handle capture mode:
def _on_key_pressed(self, ctrl, keyval, keycode, state):
    if self._capture_action:
        return self._handle_capture_key(keyval, state)
    if keyval == Gdk.KEY_Escape:
        self.close()
        return True
    return False
```

**Capture key handler:**
```python
def _handle_capture_key(self, keyval: int, state: Gdk.ModifierType) -> bool:
    from gi.repository import Gdk
    # ESC cancels capture
    if keyval == Gdk.KEY_Escape:
        self._cancel_capture()
        return True
    # Build modifier set from Gdk state
    mods = set()
    if state & Gdk.ModifierType.CONTROL_MASK: mods.add('ctrl')
    if state & Gdk.ModifierType.ALT_MASK:     mods.add('alt')
    if state & Gdk.ModifierType.SHIFT_MASK:   mods.add('shift')
    if state & Gdk.ModifierType.SUPER_MASK:   mods.add('super')
    # Reject bare modifier presses
    if keyval in _GTK_MODIFIER_KEYSYMS:
        return True
    # Require at least one modifier
    if not mods:
        return True
    # Build key identifier
    key_id = _gdk_keyval_to_id(keyval)
    if key_id is None:
        return True
    combo_str = '+'.join(sorted(mods, key=lambda m: ['ctrl','alt','shift','super'].index(m))) + '+' + key_id
    self._accept_capture(combo_str)
    return True
```

**Gdk keyval to pynput-compatible key_id mapping:**
```python
_GDK_SPECIAL_KEY_MAP = {
    Gdk.KEY_Escape: 'esc',
    Gdk.KEY_Delete: 'delete',
    Gdk.KEY_Return: 'enter',
    Gdk.KEY_Tab: 'tab',
    Gdk.KEY_space: 'space',
    Gdk.KEY_Left: 'left', Gdk.KEY_Right: 'right',
    Gdk.KEY_Up: 'up', Gdk.KEY_Down: 'down',
    Gdk.KEY_Home: 'home', Gdk.KEY_End: 'end',
    Gdk.KEY_Page_Up: 'page_up', Gdk.KEY_Page_Down: 'page_down',
    Gdk.KEY_Insert: 'insert',
    Gdk.KEY_F1: 'f1', Gdk.KEY_F2: 'f2', Gdk.KEY_F3: 'f3',
    Gdk.KEY_F4: 'f4', Gdk.KEY_F5: 'f5', Gdk.KEY_F6: 'f6',
    Gdk.KEY_F7: 'f7', Gdk.KEY_F8: 'f8', Gdk.KEY_F9: 'f9',
    Gdk.KEY_F10: 'f10', Gdk.KEY_F11: 'f11', Gdk.KEY_F12: 'f12',
}

def _gdk_keyval_to_id(keyval: int) -> str | None:
    if keyval in _GDK_SPECIAL_KEY_MAP:
        return _GDK_SPECIAL_KEY_MAP[keyval]
    char = chr(keyval).lower()
    if char.isalpha() or char.isdigit():
        return char
    return None
```

### Pattern 4: Conflict Detection

```python
HOTKEY_ACTION_LABELS = {
    'record':       'Record Toggle',
    'stop':         'Stop Recording',
    'conversation': 'Conversation Mode',
    'reprocess':    'Reprocess Failed',
    'feedback':     'Feedback Toggle',
}

DANGEROUS_COMBOS = {
    'ctrl+alt+delete',
    'ctrl+alt+left', 'ctrl+alt+right',
    'ctrl+alt+f1', 'ctrl+alt+f2', 'ctrl+alt+f3', 'ctrl+alt+f4',
    'ctrl+alt+f5', 'ctrl+alt+f6', 'ctrl+alt+f7', 'ctrl+alt+f8',
    'ctrl+alt+f9', 'ctrl+alt+f10', 'ctrl+alt+f11', 'ctrl+alt+f12',
}

def _check_conflict(self, new_combo: str, editing_action: str) -> str | None:
    """Return error message if conflict, None if clean."""
    if new_combo in DANGEROUS_COMBOS:
        return f"{combo_display(new_combo)} is reserved by the system"
    for action, btn in self._capture_buttons.items():
        if action == editing_action:
            continue
        current = self._hotkey_values.get(action, '')
        if current == new_combo:
            return f"{combo_display(new_combo)} is already used for {HOTKEY_ACTION_LABELS[action]}"
    return None
```

### Pattern 5: Hot-Reload Integration (app.py)

**What:** After SettingsWindow saves, notify HotkeyManager to reload. The simplest approach is a callback parameter on SettingsWindow (consistent with how settings already works) or calling `reload_bindings()` directly in `_on_settings_closed`.

```python
# In app.py _on_settings_closed:
def _on_settings_closed(self, _window):
    self._settings = None
    if self._hotkey_manager:
        self._hotkey_manager.reload_bindings()
    return False
```

This is safe: `_on_settings_closed` runs on the GTK main thread, and `reload_bindings()` only writes to `self._bindings` (read from the pynput thread). Python GIL makes a single dict reassignment atomic enough for this pattern. For extra safety, a threading.Lock can guard `self._bindings`, but the existing codebase has no locking precedent.

### Anti-Patterns to Avoid

- **Blocking the pynput listener thread with config I/O:** `reload_bindings()` must only be called from GTK main thread or must complete quickly (load_config is file I/O — acceptable, but call from main thread via idle_add if triggered from listener).
- **Using Gtk.Dialog for capture:** Project pattern is Gtk.Window(modal=True), and GTK 4.10 deprecated Gtk.Dialog.
- **Stopping and restarting the pynput Listener:** Expensive and racy. Reload bindings in place instead.
- **Using keyboard.Listener suppress=True:** Crashes X11 sessions (documented in STATE.md, [02-04]).
- **Calling GTK functions from pynput listener thread without GLib.idle_add:** The threading contract in HotkeyManager docstring is explicit.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Key name display | Custom keysym lookup | `Gdk.keyval_name(keyval)` for debugging; manual display map for user-visible strings | Gdk.keyval_name returns X11 internal names not suitable for display ("Control_L" not "Ctrl") |
| GTK modifier detection | Parsing raw key events | `Gdk.ModifierType` flags from EventControllerKey `state` parameter | Gdk handles platform differences |
| Config persistence | New storage mechanism | Existing `load_config()` / `save_config()` | Already handles JSON, backfill, permissions |
| Default backfill | Migration code | Add to `DEFAULT_CONFIG` dict | `load_config()` already merges defaults into existing configs |

**Key insight:** The capture UI requires custom logic (there is no "hotkey capture widget" in GTK4 stdlib), but GTK4's EventControllerKey makes it clean. The key-matching in pynput requires a custom comparison function but is straightforward given pynput's stable API.

## Common Pitfalls

### Pitfall 1: GTK EventControllerKey Focus Requirement
**What goes wrong:** Key events are not delivered to SettingsWindow's EventControllerKey if the capture button retains focus (buttons consume key events before the window controller sees them).
**Why it happens:** GTK4 event propagation — child widget controllers fire before window-level controllers by default, and focused buttons eat key events.
**How to avoid:** After entering capture mode, call `self.set_focus(None)` or give focus to an unfocusable widget so the window-level EventControllerKey receives all keystrokes.
**Warning signs:** Capture button still shows "Press keys..." after pressing a combo — means the key event was consumed by the button widget, not the window controller.

### Pitfall 2: Modifier-Only Key Presses Triggering Capture
**What goes wrong:** User presses Ctrl alone (without any other key) and capture accepts "ctrl" as a binding.
**Why it happens:** GTK fires key-pressed for modifier keys too (Gdk.KEY_Control_L, etc.).
**How to avoid:** Filter out keyvals corresponding to modifiers before processing. Build `_GTK_MODIFIER_KEYSYMS` set:
```python
_GTK_MODIFIER_KEYSYMS = {
    Gdk.KEY_Control_L, Gdk.KEY_Control_R,
    Gdk.KEY_Alt_L, Gdk.KEY_Alt_R,
    Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
    Gdk.KEY_Super_L, Gdk.KEY_Super_R,
    Gdk.KEY_ISO_Level3_Shift,  # AltGr
    Gdk.KEY_Caps_Lock, Gdk.KEY_Num_Lock,
}
```

### Pitfall 3: pynput Modifier Key Enum Aliases
**What goes wrong:** Code checks `key == keyboard.Key.ctrl_l` but on some platforms Key.ctrl_l is an alias for Key.ctrl, causing double-matching or missed detection.
**Why it happens:** pynput Key enum has left/right variants that may resolve to a single enum member on X11.
**How to avoid:** In `_on_press`, check against a dict keyed by `keyboard.Key` members (the MODIFIER_MAP pattern above), not individual comparisons. The dict lookup handles aliases automatically since equal enum members hash the same.
**Warning signs:** Tests pass but live key detection breaks for right-side modifier keys.

### Pitfall 4: history_window.py Stale Config Key Reference
**What goes wrong:** `history_window.py:189` reads `cfg.get('hotkey_record', 'F9')` — this key does not exist in DEFAULT_CONFIG (uses 'F9' default which is wrong post-Phase 2).
**Why it happens:** Pre-existing bug identified in CONTEXT.md code insights section.
**How to avoid:** Update `history_window.py:189` to use the new `hotkey_record` config key and read its display value properly. Fix must be included in this phase.
**Warning signs:** Empty history view shows "Press F9 to start recording" instead of the configured hotkey display string.

### Pitfall 5: Combo Ordering in Serialization
**What goes wrong:** "alt+ctrl+r" and "ctrl+alt+r" are the same combo but compare as different strings.
**Why it happens:** String split and join without canonical ordering.
**How to avoid:** Always serialize modifiers in a fixed order: `ctrl` < `alt` < `shift` < `super`. Comparison functions should sort before comparing. When accepting a capture result, canonicalize immediately.

### Pitfall 6: Reset-to-Default Doesn't Hot-Reload
**What goes wrong:** Per-hotkey reset button updates the UI and internal state but the new binding isn't active until Save is clicked.
**Why it happens:** CONTEXT.md says both per-hotkey reset and Reset All "apply immediately (same hot-reload as capture)".
**How to avoid:** Per-hotkey reset must call the same `_apply_binding(action, combo_str)` helper that capture acceptance calls — which updates UI, internal state dict, AND calls `hotkey_manager.reload_bindings()`.

## Code Examples

Verified patterns from existing codebase:

### Settings Section Pattern (from settings.py)
```python
# Source: src/linux_speech_flow/settings.py - existing section structure
sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
sep.set_margin_top(8)
sep.set_margin_bottom(8)
content.append(sep)

title = Gtk.Label(label="Hotkeys")
title.add_css_class("title-4")
title.set_xalign(0)
content.append(title)

# Row pattern
row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
label = Gtk.Label(label="Record Toggle")
label.set_hexpand(True)
label.set_xalign(0)
btn = Gtk.Button(label="Ctrl+Alt+R")
row.append(label)
row.append(btn)
content.append(row)
```

### Config Default Backfill (from config.py load_config)
```python
# Source: src/linux_speech_flow/config.py
# New keys in DEFAULT_CONFIG are automatically backfilled into existing user configs:
def load_config(*, _path: Path = CONFIG_PATH) -> dict:
    config = dict(DEFAULT_CONFIG)   # start with all defaults
    if _path.exists():
        with open(_path) as f:
            data = json.load(f)
        config.update(data)         # user values override defaults
    return config
# No migration code needed — this is the established backfill pattern.
```

### GLib.idle_add Threading Pattern (from hotkey.py)
```python
# Source: src/linux_speech_flow/hotkey.py
# pynput callback -> GTK main thread bridge:
if key == keyboard.Key.esc and self._state == self._STATE_RECORDING:
    GLib.idle_add(self._stop_recording, False)
    return
```

### Settings Dirty Tracking (from settings.py _connect_change_signals)
```python
# Source: src/linux_speech_flow/settings.py
# Pattern for connecting change signals to mark_dirty:
def _connect_change_signals(self):
    md = self._mark_dirty
    self._api_key_entry.connect("changed", md)
    # ... each widget connected similarly
    # Hotkey buttons don't use standard GTK change signals —
    # _mark_dirty() must be called explicitly in _accept_capture()
```

### EventControllerKey (from settings.py __init__)
```python
# Source: src/linux_speech_flow/settings.py - existing key controller
key_ctrl = Gtk.EventControllerKey()
key_ctrl.connect("key-pressed", self._on_key_pressed)
self.add_controller(key_ctrl)

# Current _on_key_pressed — to be extended:
def _on_key_pressed(self, _ctrl, keyval, _keycode, _state):
    if keyval == Gdk.KEY_Escape:
        self.close()
        return True
    return False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded Ctrl+Alt+R/C/P/F in _on_press | Config-driven binding dict with _matches_binding() | Phase 7 | HotkeyManager becomes data-driven |
| _ctrl_held + _alt_held booleans | _modifiers_held set tracking all 4 modifier types | Phase 7 | Supports Shift+, Super+ combos |
| history_window reads 'hotkey_record' default 'F9' | Reads actual config value + calls combo_display() | Phase 7 bugfix | Shows correct hotkey in empty history hint |

**Deprecated/outdated:**
- `_ctrl_held` / `_alt_held` instance variables: replaced by `_modifiers_held` set
- `conv_hotkey_start` / `conv_hotkey_feedback` config keys: already removed in commit 6ff4ff6

## Open Questions

1. **HotkeyManager thread safety for `_bindings` dict reassignment**
   - What we know: Python GIL makes single assignment atomic; pynput listener reads `_bindings` frequently
   - What's unclear: Whether the GIL guarantee is sufficient or a threading.Lock is needed
   - Recommendation: Single dict reassignment in `reload_bindings()` is atomic under CPython's GIL; skip the lock to keep code simple and consistent with the rest of the codebase (which uses no locks)

2. **Super/Meta key support on X11**
   - What we know: pynput exposes `Key.cmd` / `Key.cmd_r` for the Super/Windows key; it works on X11 in the existing project
   - What's unclear: Whether Super combos are captured reliably by GTK's EventControllerKey on all desktop environments (some WMs grab Super)
   - Recommendation: Support Super in the implementation but document in UI that Super combos may be intercepted by the window manager

3. **Stop recording binding uniqueness**
   - What we know: CONTEXT.md says stop binding is a full combo like all others (not a bare ESC)
   - What's unclear: The current `hotkey_record` and `hotkey_stop` would by default both be "ctrl+alt+r" (record is a toggle). Should stop default differ?
   - Recommendation: Default `hotkey_record` to "ctrl+alt+r" (toggle — starts AND stops). Default `hotkey_stop` to "ctrl+alt+r" as well (same key, different semantic). This mirrors current behavior where Ctrl+Alt+R stops too. A distinct stop default (e.g. "ctrl+alt+s") would be cleaner but changes existing UX.

## Sources

### Primary (HIGH confidence)
- Directly read: `src/linux_speech_flow/hotkey.py` — current binding implementation
- Directly read: `src/linux_speech_flow/config.py` — DEFAULT_CONFIG + load/save pattern
- Directly read: `src/linux_speech_flow/settings.py` — section patterns + EventControllerKey
- Directly read: `src/linux_speech_flow/app.py` — HotkeyManager construction + settings wiring
- Directly read: `tests/test_hotkey.py` — existing test patterns for HotkeyManager
- Directly read: `.planning/phases/07-hotkey-customization/07-CONTEXT.md` — user decisions
- Verified via project venv: pynput Key enum members, KeyCode.from_char, Key name attributes
- Verified via project venv: All modifier key aliases (ctrl_l == ctrl, etc.)
- Verified via project venv: Dangerous combo key names (delete, left, right, f1-f12)

### Secondary (MEDIUM confidence)
- GTK4 EventControllerKey behavior for key capture: pattern derived from existing settings.py usage + GTK4 documentation knowledge
- Gdk.ModifierType flags for modifier detection: standard GTK4 pattern

### Tertiary (LOW confidence)
- Super/Win key capture reliability across desktop environments: known limitation, not verified against specific DEs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, verified via venv
- Architecture: HIGH — patterns derived directly from reading existing codebase
- Pitfalls: HIGH for GTK focus/modifier issues (verified via code inspection), MEDIUM for pynput thread safety
- Config serialization: HIGH — straightforward string format, no external dependencies

**Research date:** 2026-03-03
**Valid until:** 2026-06-03 (pynput and GTK4 APIs are stable; no fast-moving dependencies)
