# Phase 4: System Tray & Desktop Integration - Research

**Researched:** 2026-02-21
**Domain:** Linux system tray (StatusNotifierItem/D-Bus), GTK4 integration, icon themes, XDG autostart
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tray icon states:**
- 4 states: idle (grey) / recording (red pulse) / processing (yellow spin) / error (red with X)
- Recording and processing states are animated — frame-swapping via GLib.timeout_add timer
- Error state clears automatically when user presses F9 to start a new recording
- Error state is set by any Whisper API failure (auth error, network error, rate limit)

**App window behavior:**
- Remove the placeholder window entirely — app runs headless in Phase 4
- App stays alive via `Gtk.Application.hold()` (prevents auto-quit when no windows open)
- Left-click on tray icon opens the menu
- Right-click opens Settings window (best-effort via `secondary-activate` signal; fallback to menu if unsupported by desktop)
- Quit is only available via the tray menu (no window close button)
- Add XDG autostart `.desktop` file to `~/.config/autostart/` for development use, pointing to the venv Python

**Tray menu contents and order:**
- Flat menu, no separators: Settings / Open Debug Log / Reprocess Failed (N) / Quit
- "Reprocess Failed (N)" shows live count of WAVs in the failed/ directory
- "Reprocess Failed" is greyed out when count is 0
- Count updates in real-time: pipeline calls a callback when a WAV is saved to failed/ or cleared after reprocess
- "Reprocess Failed" triggers the same F10 logic as the hotkey (single WAV = auto-paste, multiple = dialog)

### Claude's Discretion
- Animation frame count, frame rate, and SVG icon design for each state
- Implementation of right-click Settings (secondary-activate vs alternative approach)
- Mechanism for passing failed-count change callback from TranscriptionPipeline to TrayManager
- Whether to use icon theme names or direct SVG file paths for AppIndicator3
- AppIndicator3 vs AyatanaAppIndicator3 try/except fallback (already decided in STATE.md)

### Deferred Ideas (OUT OF SCOPE)
- **CLI binary (`/usr/bin/linux-speech-flow`)** — Phase 6
- **Installer script for .deb** — Phase 6
- **Bundled venv in .deb** — Phase 6
- **View Run Log tray menu item** — Phase 5 (Pipeline History delivers the history viewer)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRAY-01 | Application icon appears in system tray on launch (AppIndicator3/AyatanaAppIndicator3 with dual-library fallback) | Use `trayer` library (StatusNotifierItem protocol) instead — AppIndicator3 is incompatible with GTK4 in the same process. `trayer` confirmed working on the target system. |
| TRAY-02 | Tray icon changes state visually during recording and transcribing phases | Frame-swapping via `TrayIcon.change_icon()` + `GLib.timeout_add()`. Requires bundled SVG icons installed to `~/.local/share/icons/hicolor/scalable/status/`. |
| TRAY-03 | Desktop notification appears on error (API failure, mic unavailable, etc.) via libnotify/notify-send | `send_notification()` already exists in `notify.py` and is already called from `transcription.py` and `hotkey.py`. Phase 4 ensures these paths are wired correctly and the error state drives the tray icon to the error state. |
| TRAY-04 | Tray menu includes: View Run Log, Settings, Quit | `trayer` menu supports `add_menu_item(label, callback, enabled=True/False)`. Dynamic "Reprocess Failed (N)" via dict mutation + `update_menu()`. "Open Debug Log" replaces "View Run Log" per CONTEXT.md (Phase 5 adds history). |
</phase_requirements>

## Summary

The central architectural challenge for Phase 4 is that **AppIndicator3 and AyatanaAppIndicator3 both require GTK3, which cannot coexist with GTK4 in the same Python process**. The app uses GTK4 throughout (`.append()`, `.set_child()`, `Gtk.FileChooserNative`, `Gtk.EventControllerScroll`), and migrating all windows to GTK3 would touch every window file with ~150 line changes — that is the wrong direction.

The solution is the `trayer` library (version 0.1.1, MIT, 2025), a pure-Python implementation of the `org.kde.StatusNotifierItem` D-Bus protocol. It requires only `dbus-python` (the system package `python3-dbus`, already installed) and `PyGObject` (already in the venv). It integrates with the GLib main loop (which GTK4's `app.run()` drives) by setting `dbus.mainloop.glib.DBusGMainLoop` as the D-Bus main loop before calling `tray.setup()`. The `StatusNotifierWatcher` service (`org.kde.StatusNotifierWatcher`) is confirmed running on the target system, and `trayer` registers with it successfully.

Icon animation is achieved by calling `TrayIcon.change_icon(name)` on a `GLib.timeout_add()` timer. Custom icons must be in the XDG icon theme (scalable SVGs placed in `~/.local/share/icons/hicolor/scalable/status/`), which the app installs from bundled package data at startup. The failed-count menu item is driven by a new `on_failed_count_changed` callback added to `TranscriptionPipeline`, which mutates a held dict reference and calls `tray.update_menu()`.

**Primary recommendation:** Use `trayer` 0.1.1 for the tray icon (StatusNotifierItem over D-Bus). Bundle 8 SVG icons as package data, install them to the user icon theme at startup. Add `on_recording_start` to `HotkeyManager` and `on_failed_count_changed` to `TranscriptionPipeline`. Left-click opens Settings (the menu handles everything else).

---

## Critical Architecture Finding: AppIndicator3 is GTK3-only

**This directly overrides the CONTEXT.md discretion area** "AppIndicator3 vs AyatanaAppIndicator3 try/except fallback."

### Why AppIndicator3 Cannot Be Used

```python
# Confirmed on this system:
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # GTK4 loaded

# Loading AyatanaAppIndicator3 FAILS because it imports GTK3 internally:
from gi.repository import AyatanaAppIndicator3  # -> ImportError: GTK 3.0 conflicts with 4.0
```

Verified: AyatanaAppIndicator3 is installed (`gir1.2-ayatanaappindicator3-0.1`), but internally it depends on GTK3. Once GTK4 is loaded, GTK3 cannot load in the same process, and vice versa. This is a hard GObject Introspection constraint, not a version preference. No workaround exists short of:
- Running the tray in a subprocess (complex IPC)
- Migrating the entire app to GTK3 (~150 lines across 5 files, wrong direction)
- Using a GTK-version-agnostic D-Bus approach

The correct path is the D-Bus approach.

### CONTEXT.md Override

The locked decision "Left-click on tray icon opens the menu / Right-click opens Settings window via secondary-activate" must be adapted:

- `trayer` (StatusNotifierItem protocol) maps clicks as: left=`Activate`, middle=`SecondaryActivate`, right=always shows menu (`ContextMenu`)
- Right-click cannot be redirected to open Settings — it always shows the D-Bus menu
- **Planner should use: left-click opens Settings window, right-click opens menu**
- This is better UX anyway (the natural expectation for tray icons)

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `trayer` | 0.1.1 | GTK4-compatible system tray via StatusNotifierItem + DBusMenu D-Bus protocols | Only viable option for GTK4 Python apps on Linux; MIT license; confirmed working |
| `dbus-python` | 1.2.18 (system) | D-Bus Python bindings required by trayer | System package `python3-dbus`; already installed; loads from system site-packages |
| `GLib.timeout_add` | (gi.repository.GLib) | Timer for icon animation frame-swapping | Already used in project; fires on GTK main thread |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `importlib.resources` | stdlib | Bundle SVG icons in package, extract to user icon dir at startup | Same pattern as `sounds/__init__.py` already in project |
| `notify-send` / `notify.py` | existing | Error notifications | Already implemented; `send_notification()` just needs wiring to `_on_pipeline_error` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `trayer` | `pystray` | pystray 0.19.5 is available but uses X11 StatusIcon (deprecated) or AppIndicator3 backend — same GTK3 conflict |
| `trayer` | Raw D-Bus (dbus-python + hand-rolled SNI) | trayer already does this cleanly; no reason to hand-roll |
| icon theme install | Icon file path in trayer | trayer's SNI implementation only sends icon names, not paths; host DE resolves by name from theme |
| `trayer` | AppIndicator3 + GTK3 migration | Migration cost ~150 lines across 5 files; incompatible direction for GTK4 |

**Installation:**
```bash
pip install trayer==0.1.1
```

`dbus-python` is a system-only package (no PyPI wheel). It loads from `/usr/lib/python3/dist-packages/dbus/` which is on the venv sys.path. For `.deb` packaging (Phase 6), add `python3-dbus` as a `Depends:` entry.

---

## Architecture Patterns

### Recommended Project Structure

```
src/linux_speech_flow/
├── app.py              # Modified: remove placeholder window, add hold(), TrayManager wiring
├── hotkey.py           # Modified: add on_recording_start callback
├── transcription.py    # Modified: add on_failed_count_changed callback
├── tray.py             # NEW: TrayManager class (trayer wrapper + animation + state)
├── icons/              # NEW: bundled SVG icon package
│   ├── __init__.py
│   ├── freeflow-idle.svg
│   ├── freeflow-recording-1.svg
│   ├── freeflow-recording-2.svg
│   ├── freeflow-recording-3.svg
│   ├── freeflow-processing-1.svg
│   ├── freeflow-processing-2.svg
│   ├── freeflow-processing-3.svg
│   └── freeflow-error.svg
└── ...
```

### Pattern 1: trayer Setup Before app.run()

**What:** `trayer.TrayIcon.setup()` must be called before `Gtk.Application.run()`. It calls `dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)` internally, integrating D-Bus event handling with the GLib main loop.

**When to use:** In `App.do_startup()`, after constructing `TrayManager` and before `self.hold()`.

```python
# In App.do_startup():
import dbus
import dbus.mainloop.glib
from trayer import TrayIcon

# MUST call before tray.setup():
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

self._tray = TrayManager(
    app=self,
    on_settings=self._on_open_settings,
    on_debug_log=self._on_open_debug_log,
    on_reprocess=self._on_reprocess_hotkey,
)
self._tray.setup()  # registers with StatusNotifierWatcher
```

### Pattern 2: Icon Animation via Frame-Swapping

**What:** `GLib.timeout_add(interval_ms, callback)` calls the callback every `interval_ms` milliseconds. Callback returns `True` to continue, `False` to stop. Cancel with `GLib.source_remove(source_id)`. Call `tray.change_icon(name)` inside callback to advance frames.

**When to use:** When entering recording or processing state.

```python
# Source: verified against GLib docs and tested in project venv
class TrayManager:
    RECORDING_FRAMES = ['freeflow-recording-1', 'freeflow-recording-2', 'freeflow-recording-3']
    PROCESSING_FRAMES = ['freeflow-processing-1', 'freeflow-processing-2', 'freeflow-processing-3']
    RECORDING_INTERVAL_MS = 500
    PROCESSING_INTERVAL_MS = 400

    def __init__(self, ...):
        self._anim_source_id = None
        self._anim_frames = []
        self._anim_frame_idx = 0
        self._tray = TrayIcon(...)

    def _start_animation(self, frames, interval_ms):
        self._stop_animation()
        self._anim_frames = frames
        self._anim_frame_idx = 0
        self._tray.change_icon(frames[0])
        self._anim_source_id = GLib.timeout_add(interval_ms, self._advance_frame)

    def _stop_animation(self):
        if self._anim_source_id is not None:
            GLib.source_remove(self._anim_source_id)
            self._anim_source_id = None

    def _advance_frame(self):
        self._anim_frame_idx = (self._anim_frame_idx + 1) % len(self._anim_frames)
        self._tray.change_icon(self._anim_frames[self._anim_frame_idx])
        return True  # keep timer running

    def set_state(self, state: str):
        if state == 'recording':
            self._start_animation(self.RECORDING_FRAMES, self.RECORDING_INTERVAL_MS)
        elif state == 'processing':
            self._start_animation(self.PROCESSING_FRAMES, self.PROCESSING_INTERVAL_MS)
        elif state == 'idle':
            self._stop_animation()
            self._tray.change_icon('freeflow-idle')
        elif state == 'error':
            self._stop_animation()
            self._tray.change_icon('freeflow-error')
```

### Pattern 3: Dynamic Menu Item (Failed Count)

**What:** `trayer` stores menu items as plain dicts in `TrayIcon.menu_items`. Mutate in-place and call `tray.update_menu()` to signal the D-Bus host to refresh.

**When to use:** Whenever the failed WAV count changes (pipeline saves a failed WAV or successfully reprocesses one).

```python
# In TrayManager.__init__():
self._reprocess_item = {
    'type': 'item',
    'label': 'Reprocess Failed (0)',
    'callback': on_reprocess,
    'enabled': False,
    'visible': True,
}
self._tray.menu_items = [
    {'type': 'item', 'label': 'Settings', 'callback': on_settings, 'enabled': True, 'visible': True},
    {'type': 'item', 'label': 'Open Debug Log', 'callback': on_debug_log, 'enabled': True, 'visible': True},
    self._reprocess_item,  # reference held for mutation
    {'type': 'item', 'label': 'Quit', 'callback': on_quit, 'enabled': True, 'visible': True},
]

# Called when count changes:
def update_failed_count(self, count: int):
    self._reprocess_item['label'] = f'Reprocess Failed ({count})'
    self._reprocess_item['enabled'] = count > 0
    self._tray.update_menu()
```

### Pattern 4: Icon Installation at Startup

**What:** Bundle SVG icons as package data (like `sounds/*.wav`). At startup, copy to `~/.local/share/icons/hicolor/scalable/status/` using `importlib.resources`.

**When to use:** In `App.do_startup()`, before `TrayManager.setup()`.

```python
# In a new icons/__init__.py or tray.py:
import importlib.resources
import shutil
from pathlib import Path

ICON_NAMES = [
    'freeflow-idle',
    'freeflow-recording-1', 'freeflow-recording-2', 'freeflow-recording-3',
    'freeflow-processing-1', 'freeflow-processing-2', 'freeflow-processing-3',
    'freeflow-error',
]

def install_icons():
    dest_dir = Path.home() / '.local' / 'share' / 'icons' / 'hicolor' / 'scalable' / 'status'
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in ICON_NAMES:
        filename = f'{name}.svg'
        ref = importlib.resources.files('linux_speech_flow.icons').joinpath(filename)
        with importlib.resources.as_file(ref) as src:
            dest = dest_dir / filename
            if not dest.exists():
                shutil.copy2(src, dest)
```

`pyproject.toml` addition:
```toml
[tool.setuptools.package-data]
linux_speech_flow = ["sounds/*.wav", "icons/*.svg"]
```

### Pattern 5: TranscriptionPipeline Failed Count Callback

**What:** Add `on_failed_count_changed(count: int)` callback to `TranscriptionPipeline`. Fire it after `_save_failed_wav()` (count increases) and after a successful reprocess WAV unlink (count decreases).

```python
# In TranscriptionPipeline.__init__:
def __init__(self, on_paste_complete=None, on_error=None, on_failed_count_changed=None):
    self._on_failed_count_changed = on_failed_count_changed
    ...

def _get_failed_count(self) -> int:
    return len(list(FAILED_DIR.glob('*.wav'))) if FAILED_DIR.exists() else 0

def _notify_failed_count(self):
    if self._on_failed_count_changed:
        count = self._get_failed_count()
        GLib.idle_add(self._on_failed_count_changed, count)

# After _save_failed_wav():
self._notify_failed_count()

# After os.unlink(wav_path) when wav_path startswith str(FAILED_DIR):
self._notify_failed_count()
```

### Pattern 6: HotkeyManager Recording-Start Callback

**What:** Add `on_recording_start` callback to drive tray to recording state immediately when F9 is pressed.

```python
# In HotkeyManager.__init__:
def __init__(self, on_recording_start=None, on_recording_complete=None, on_recording_error=None, on_reprocess=None):
    self._on_recording_start_cb = on_recording_start
    ...

# In _start_recording():
self._state = self._STATE_RECORDING
if self._on_recording_start_cb:
    self._on_recording_start_cb()  # already on GTK main thread
```

### Pattern 7: XDG Autostart Desktop File

**What:** A `.desktop` file in `~/.config/autostart/` launches the app at login. For development, it uses the absolute venv Python path.

```ini
[Desktop Entry]
Name=FreeFlow
Comment=Linux speech-to-text assistant
Exec=/home/jon/projects/linux-speech-flow/.venv/bin/python -m linux_speech_flow
Icon=freeflow-idle
Type=Application
StartupNotify=false
X-GNOME-Autostart-enabled=true
```

Install in `do_startup()` (or a separate setup step). Phase 6 replaces `Exec=` with `/usr/bin/linux-speech-flow`.

### Anti-Patterns to Avoid

- **Loading GTK before AppIndicator3 (or vice versa):** Any attempt to use both GTK3 and GTK4 namespaces in one process raises `ValueError: Namespace Gtk is already loaded with version X.Y`. Do not attempt.
- **Calling `tray.setup()` inside `do_activate()`:** `setup()` initializes the D-Bus connection. It must precede `app.run()` being in the main loop phase. Call in `do_startup()`.
- **Direct file path as icon name:** `trayer` sends `IconName` as a D-Bus string; the DE host resolves it via the icon theme. Absolute paths are not supported. Use the XDG icon installation pattern.
- **Returning `None` from `GLib.timeout_add` callback:** Must return `True` to keep the timer running; `False` or `None` stops it. Returning `None` will silently stop animation.
- **Forgetting `GLib.source_remove()` on state transition:** Not removing the old timer when switching states causes multiple timers to fire simultaneously, corrupting animation.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| StatusNotifierItem D-Bus protocol | Custom D-Bus SNI service | `trayer` 0.1.1 | SNI has 7 D-Bus methods + signals; DBusMenu adds 5 more; trayer handles all this |
| Animation loop | `threading.Thread` with `time.sleep` | `GLib.timeout_add()` | Thread would need thread-safe tray calls; GLib timer runs on GTK main thread, no locks needed |
| Failed WAV count watch | `inotify`/directory polling | Direct count from `on_failed_count_changed` callback | Polling adds overhead and timing gaps; callback fires at exact moment count changes |
| Desktop notification | `subprocess.run(['notify-send', ...])` | Existing `send_notification()` in `notify.py` | Already implemented and tested with replace_id support |

---

## Common Pitfalls

### Pitfall 1: DBusGMainLoop Must Be Set Before tray.setup()

**What goes wrong:** D-Bus events are not integrated with GLib main loop; tray appears but menu clicks don't fire.

**Why it happens:** `dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)` is not called before any D-Bus object is created.

**How to avoid:** Call `dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)` at module level in `tray.py` or at the very start of `TrayManager.__init__()`. trayer's `setup()` also calls it, but it must be the first D-Bus operation.

**Warning signs:** `dbus.exceptions.DBusException` at registration time; or menu item callbacks never fire.

### Pitfall 2: Icon Not Found in Tray

**What goes wrong:** Tray icon shows a generic "unknown" icon or no icon at all.

**Why it happens:** SVGs not installed to `~/.local/share/icons/hicolor/scalable/status/` before `tray.setup()` is called. The D-Bus host resolves icon names lazily, but if the icon is missing, it falls back to a generic icon.

**How to avoid:** Call `install_icons()` in `do_startup()` before creating `TrayManager`. Verify destination path exists.

**Warning signs:** Generic microphone icon in tray; no `freeflow-*` icons in `~/.local/share/icons/hicolor/scalable/status/`.

### Pitfall 3: Multiple Animation Timers Running Simultaneously

**What goes wrong:** Icon flickers or animates faster than expected; memory of `source_id` lost.

**Why it happens:** `set_state()` called multiple times without `_stop_animation()` removing the previous timer.

**How to avoid:** Always call `_stop_animation()` at the top of `_start_animation()`. Track `_anim_source_id` as instance variable; set to `None` after `source_remove`.

### Pitfall 4: GLib.idle_add Callback Must Return False

**What goes wrong:** Callback registered with `GLib.idle_add` keeps firing indefinitely.

**Why it happens:** Returning `True` from an `idle_add` callback re-schedules it. `on_failed_count_changed` wired via `GLib.idle_add` must return `False` (or the wrapper in `TrayManager.update_failed_count` must use `GLib.idle_add(self.update_failed_count, count)` where `update_failed_count` returns `False`).

**How to avoid:** Use the established project pattern: callbacks dispatched via `GLib.idle_add` must explicitly `return False`.

### Pitfall 5: trayer's `update_menu()` Does Not Rebuild menu_items

**What goes wrong:** Menu shows stale label/enabled state.

**Why it happens:** `update_menu()` increments `revision` and emits `LayoutUpdated`, telling the host to re-fetch. But it re-fetches from `self.menu_items` — so mutating the dict must happen BEFORE `update_menu()`.

**How to avoid:** Mutate the dict reference first, then call `update_menu()`. Always hold a reference to mutable items (like `self._reprocess_item`).

### Pitfall 6: `trayer` Is a Young Library (Confidence Flag)

**What goes wrong:** API may change; limited documentation; single maintainer.

**Why it matters:** `trayer` 0.1.1 has 1 star on GitHub (as of 2025). The SNI protocol it implements is stable, but the Python wrapper is new.

**Mitigation:** The library is small (1 file, ~450 lines) and fully readable. If it breaks, the project can vendor the file or re-implement directly. Pin version in `pyproject.toml`.

---

## Code Examples

### Minimal TrayManager Skeleton

```python
# src/linux_speech_flow/tray.py
import logging
import dbus
import dbus.mainloop.glib
from gi.repository import GLib
from trayer import TrayIcon

logger = logging.getLogger(__name__)

RECORDING_FRAMES = ['freeflow-recording-1', 'freeflow-recording-2', 'freeflow-recording-3']
PROCESSING_FRAMES = ['freeflow-processing-1', 'freeflow-processing-2', 'freeflow-processing-3']
RECORDING_INTERVAL_MS = 500
PROCESSING_INTERVAL_MS = 400

class TrayManager:
    def __init__(self, app, on_settings, on_debug_log, on_reprocess):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        self._reprocess_item = {
            'type': 'item', 'label': 'Reprocess Failed (0)',
            'callback': on_reprocess, 'enabled': False, 'visible': True,
        }
        self._tray = TrayIcon(
            app_id='com.github.linux-speech-flow',
            title='FreeFlow',
            icon_name='freeflow-idle',
        )
        self._tray.menu_items = [
            {'type': 'item', 'label': 'Settings', 'callback': on_settings, 'enabled': True, 'visible': True},
            {'type': 'item', 'label': 'Open Debug Log', 'callback': on_debug_log, 'enabled': True, 'visible': True},
            self._reprocess_item,
            {'type': 'item', 'label': 'Quit', 'callback': app.quit, 'enabled': True, 'visible': True},
        ]
        self._tray.set_left_click(on_settings)

        self._anim_source_id = None
        self._anim_frames = []
        self._anim_frame_idx = 0

    def setup(self):
        self._tray.setup()

    def set_state(self, state: str):
        if state == 'recording':
            self._start_animation(RECORDING_FRAMES, RECORDING_INTERVAL_MS)
        elif state == 'processing':
            self._start_animation(PROCESSING_FRAMES, PROCESSING_INTERVAL_MS)
        elif state == 'idle':
            self._stop_animation()
            self._tray.change_icon('freeflow-idle')
        elif state == 'error':
            self._stop_animation()
            self._tray.change_icon('freeflow-error')

    def update_failed_count(self, count: int) -> bool:
        self._reprocess_item['label'] = f'Reprocess Failed ({count})'
        self._reprocess_item['enabled'] = count > 0
        self._tray.update_menu()
        return False  # GLib.idle_add convention

    def _start_animation(self, frames, interval_ms):
        self._stop_animation()
        self._anim_frames = frames
        self._anim_frame_idx = 0
        self._tray.change_icon(frames[0])
        self._anim_source_id = GLib.timeout_add(interval_ms, self._advance_frame)

    def _stop_animation(self):
        if self._anim_source_id is not None:
            GLib.source_remove(self._anim_source_id)
            self._anim_source_id = None

    def _advance_frame(self) -> bool:
        self._anim_frame_idx = (self._anim_frame_idx + 1) % len(self._anim_frames)
        self._tray.change_icon(self._anim_frames[self._anim_frame_idx])
        return True
```

### App.do_activate() Becomes Headless

```python
def do_activate(self):
    config = load_config()
    if not config.get('setup_complete', False):
        if self._wizard is None:
            self._wizard = WizardWindow(application=self)
            self._wizard.connect('close-request', self._on_wizard_closed)
        self._wizard.present()
    else:
        self.hold()  # headless: tray is the only presence
```

### App Tray State Wiring

```python
def _on_recording_start(self) -> None:
    if self._tray:
        self._tray.set_state('recording')

def _on_recording_complete(self, wav_path: str, stop_was_f9: bool = False) -> None:
    if self._tray:
        self._tray.set_state('processing')
    if self._pipeline:
        depth = self._pipeline.submit(wav_path, stop_was_f9=stop_was_f9)
        if depth > 1:
            send_notification('Recording queued', f'{depth} pending')

def _on_paste_complete(self) -> bool:
    if self._tray:
        self._tray.set_state('idle')
    return False

def _on_pipeline_error(self, message: str) -> None:
    if self._tray:
        self._tray.set_state('error')
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `AppIndicator3` (GTK3) | `StatusNotifierItem` D-Bus protocol | ~2018 (KDE adopted SNI); ~2022 (GTK4 made AppIndicator3 impossible) | SNI is DE-agnostic; works on GNOME+extension, KDE, XFCE, Cinnamon natively |
| `Gtk.StatusIcon` | Removed in GTK4 | GTK 4.0 (2020) | StatusIcon was X11-only; GTK4 removed it with no replacement in GTK itself |
| `gtk-update-icon-cache` (required) | Not needed for SVG/scalable | GTK 3.x+ | Scalable SVGs in user hicolor dir are found without cache regeneration |

**Deprecated/outdated:**
- `Gtk.StatusIcon`: Removed in GTK4. Do not use.
- `AppIndicator3`/`AyatanaAppIndicator3` for GTK4 apps: Incompatible — GTK3 vs GTK4 process-level conflict.
- Mixing GTK3 and GTK4 via subprocess IPC: Architecturally valid but unnecessarily complex when `trayer` solves it cleanly.

---

## Open Questions

1. **Will `trayer` icons appear on a fresh Pop!_OS GNOME install without AppIndicator extension?**
   - What we know: StateNOT.md blocker notes "Test AppIndicator extension default state on fresh Pop!_OS install before Phase 4." With `trayer` (SNI), this concern changes: SNI requires `gnome-shell-extension-appindicator` on GNOME, which is pre-installed on Pop!_OS and Ubuntu 22.04+.
   - What's unclear: Whether the extension is enabled by default vs. requiring user activation on a fresh install.
   - Recommendation: Test on a fresh Pop!_OS instance before Phase 4 merge. Add a startup check: if no SNI watcher found on bus, emit a `send_notification()` warning.

2. **Does `trayer` support icon pixmap (raw pixel data) as alternative to icon name?**
   - What we know: The SNI protocol supports `IconPixmap` property (array of width/height/data tuples). `trayer`'s current source does not implement `IconPixmap`.
   - What's unclear: Whether this would be needed if icon theme installation fails for some users.
   - Recommendation: Rely on icon theme installation. If needed later, `trayer` source is short enough to patch.

3. **Concurrent state changes — what if `set_state('processing')` fires while animation frame timer is mid-callback?**
   - What we know: Both `set_state()` and `_advance_frame()` run on the GLib main thread (GTK thread). GLib's main loop is single-threaded — callbacks don't preempt each other.
   - What's unclear: Nothing. This is safe by design.
   - Recommendation: No extra locking needed. GLib timer callbacks and `GLib.idle_add` callbacks are serialized.

---

## Sources

### Primary (HIGH confidence)

- Verified live on dev system: `trayer` 0.1.1 source at `.venv/lib/python3.10/site-packages/trayer/tray_icon.py` — full read, all methods verified
- Live Python interpreter tests: AppIndicator3/GTK4 incompatibility confirmed; trayer+GTK4 integration confirmed; dbus.mainloop.glib confirmed; GLib.timeout_add pattern confirmed; icon theme path confirmed
- System packages verified: `gir1.2-ayatanaappindicator3-0.1`, `libayatana-appindicator3-1`, `gnome-shell-extension-appindicator`, `python3-dbus` all confirmed installed
- D-Bus service verified: `org.kde.StatusNotifierWatcher` confirmed running on session bus

### Secondary (MEDIUM confidence)

- [Taiko2k/Tauon issue #1316](https://github.com/Taiko2k/Tauon/issues/1316) — confirms GTK3/GTK4 cannot coexist for AppIndicator; SNI as solution
- [GNOME Discourse: StatusIcon in GTK4](https://discourse.gnome.org/t/what-to-use-instead-of-statusicon-in-gtk4-to-display-the-icon-in-the-system-tray/7175) — GNOME's official stance; AppIndicator mentioned as community solution
- [tauri-apps/libappindicator-rs#27](https://github.com/tauri-apps/libappindicator-rs/issues/27) — upstream C library (libayatana-appindicator) confirmed not GTK4 compatible

### Tertiary (LOW confidence)

- WebSearch results 2025: general confirmation that GTK4 + AppIndicator3 incompatibility is a known ecosystem issue with no official resolution from the AppIndicator maintainers.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `trayer` tested live in project venv; GTK4 incompatibility confirmed empirically; dbus-python availability confirmed
- Architecture: HIGH — all patterns tested in Python REPL; GLib main loop integration verified; icon theme paths verified against system index.theme
- Pitfalls: HIGH — each pitfall derived from actual test failures or direct code inspection, not speculation
- Open questions: MEDIUM — question 1 is environmental (needs fresh system test); questions 2-3 are LOW risk

**Research date:** 2026-02-21
**Valid until:** 2026-08-21 (stable protocols; trayer library could update but SNI protocol won't change)
