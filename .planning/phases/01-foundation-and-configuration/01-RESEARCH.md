# Phase 1: Foundation & Configuration - Research

**Researched:** 2026-02-19
**Domain:** GTK4 Python, pyproject.toml packaging, PulseAudio device enumeration, config persistence
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Multi-step wizard (one topic per step): API key → mic selection → vocabulary list
- If user closes/cancels before finishing: wizard reopens on next launch (no config = no run)
- After Finish: wizard closes, tray icon appears — setup complete
- Vocabulary step is optional; user can skip with an empty list and add words later via Settings
- Settings window (reopened from tray menu) re-uses or mirrors the wizard; exact mode (same widget vs. flat panel) is Claude's discretion — choose simplest GTK implementation
- Validate in two passes: format check first, then a live Groq API call (e.g., list models endpoint)
- Cannot advance past the API key step on failure — inline error, stay on same step
- Error messages distinguish between causes: "Invalid API key" vs. "Could not connect to Groq — check your internet connection"
- Config schema: flat list of strings — `["kubernetes", "OAuth", "linux-speech-flow"]`
- No constraints on entries — any text, any length, no validation
- Launch command: `linux-speech-flow`
- Project structure: fresh Python project from scratch using `pyproject.toml` + `src/` layout
- Python version: 3.11+
- Config directory: `~/.config/linux-speech-flow/config.json` (with 0600 permissions)
- Data directory: `~/.local/share/linux-speech-flow/` (for future phases)
- Single-instance: if already running, silently ignore second launch (lock file or socket)
- Startup sequence on first run: wizard appears first → after Finish → tray starts

### Claude's Discretion

- GTK wizard layout (Gtk.Assistant vs. custom multi-page Gtk.Window)
- Spinner/loading UX during API key validation
- API key field masking implementation
- Vocabulary input widget (text area vs. tag-style)
- Python package name (recommend: `linux_speech_flow`)
- Vocabulary prompt strategy for Phase 3 (recommend: exact spelling enforcement)
- Settings window implementation (same widget reused vs. separate simple panel)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONF-01 | On first launch, GTK setup wizard prompts user to enter Groq API key and validates it | GTK4 Gtk.Stack wizard pattern; Groq /v1/models endpoint; Gtk.PasswordEntry with show_peek_icon; threading + GLib.idle_add for async validation |
| CONF-02 | Setup wizard allows user to select microphone from available PulseAudio/PipeWire sources | pulsectl source_list() via subprocess pactl or pulsectl library; Gtk.DropDown or Gtk.ComboBoxText for selection |
| CONF-03 | Settings are persisted to ~/.config/linux-speech-flow/config.json with 0600 permissions | json stdlib; os.chmod(path, 0o600); pathlib.Path for XDG dirs |
| CONF-04 | User can edit custom vocabulary list via settings (stored in config.json) | Gtk.TextView in scrolled window for text area input; flat list of strings in JSON |
| CONF-05 | User can select microphone from tray menu or settings (re-enumerates available sources) | pulsectl source_list() re-called on Settings open; same device enumeration function reused |
</phase_requirements>

## Summary

Phase 1 is a Python GTK4 desktop application with a multi-step first-run wizard, config persistence, and single-instance enforcement. The stack is well-understood: PyGObject (GTK4 bindings), pulsectl for audio device enumeration, requests for Groq API validation, and standard library json + pathlib for config. All components are available as system packages or pip installables.

The key architectural insight is that `Gtk.Assistant` (the "natural" wizard widget) is **deprecated since GTK 4.10** and will be removed in GTK 5. A custom `Gtk.Stack`-based wizard with manual navigation buttons is the correct forward-compatible approach. GTK4's `Gtk.Application` with default `FLAGS_NONE` provides single-instance behavior natively — the second launch triggers the first instance's `activate` signal, which re-presents the window. For audio enumeration, `pulsectl` wraps `libpulse` directly and is PipeWire-compatible via `pipewire-pulse`.

The Groq API key format is `gsk_...` (verified from GitGuardian detector docs). Validation uses `GET https://api.groq.com/openai/v1/models` — a 200 response means valid key, 401 means invalid key, connection error (`requests.exceptions.ConnectionError`) means network failure. These map cleanly to the two required error messages.

**Primary recommendation:** Use `Gtk.Application` (single-instance built-in) + `Gtk.Stack` wizard + `pulsectl` for audio + `requests` for Groq validation + stdlib `json`/`pathlib` for config.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyGObject | 3.42+ (system) | GTK4 Python bindings | Official GNOME Python binding; system-installable on Ubuntu 22.04+ |
| GTK 4 | 4.6+ (system) | GUI toolkit | Available system-wide; 4.6.9 confirmed on Ubuntu 22.04 |
| requests | 2.31+ | Groq API validation HTTP call | Standard HTTP client; maintained, PEP 668-safe via venv |
| pulsectl | 24.12.0 | Enumerate PulseAudio/PipeWire sources | libpulse bindings; source_list() and sink_list() APIs; PipeWire-compat via pipewire-pulse |
| setuptools | >=68 | pyproject.toml build backend | Standard; auto-discovers src/ layout |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | optional | Dev-time env var loading | Skip — not needed; API key stored in config.json |
| fcntl (stdlib) | stdlib | Single-instance lock file fallback | If not using Gtk.Application's native single-instance |
| pathlib (stdlib) | stdlib | XDG directory creation | Use Path.mkdir(parents=True, exist_ok=True) |
| json (stdlib) | stdlib | Config read/write | Sufficient for flat config structure |
| threading (stdlib) | stdlib | Background Groq API validation | Required for non-blocking GTK UI |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pulsectl | subprocess + pactl | pactl output parsing is brittle; pulsectl is structured API |
| pulsectl | pasimple | pasimple does NOT support device enumeration (confirmed) |
| Gtk.Stack wizard | Gtk.Assistant | Gtk.Assistant deprecated since GTK 4.10, removed in GTK 5 |
| Gtk.Application single-instance | fcntl lock file | Gtk.Application handles it natively with D-Bus; simpler |
| requests | httpx | requests is sufficient; httpx async adds complexity without benefit here |
| setuptools | hatchling | setuptools auto-discovers src/ layout; either works, setuptools more common |

**Installation:**
```bash
# System packages (must be system-installed for PyGObject)
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 libpulse-dev

# pip packages (in venv)
pip install requests pulsectl setuptools build
```

## Architecture Patterns

### Recommended Project Structure
```
linux-speech-flow/
├── pyproject.toml
├── src/
│   └── linux_speech_flow/
│       ├── __init__.py
│       ├── __main__.py          # entry: python -m linux_speech_flow
│       ├── app.py               # Gtk.Application subclass
│       ├── config.py            # Config read/write, XDG paths
│       ├── wizard.py            # First-run wizard (Gtk.Stack-based)
│       ├── settings.py          # Settings window (reuses wizard pages)
│       ├── audio.py             # pulsectl device enumeration
│       └── groq_client.py       # API key validation
├── tests/
└── README.md
```

### Pattern 1: Gtk.Application Single-Instance (Native)

**What:** `Gtk.Application` with `FLAGS_NONE` (default) enforces single-instance via D-Bus. Second launch sends `activate` signal to first instance, then exits. First instance re-presents wizard or no-ops.

**When to use:** Always — eliminates need for manual lock files.

```python
# Source: https://pygobject.gnome.org/tutorials/gtk4/application
import sys
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio

class App(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.linux-speech-flow",
            flags=Gio.ApplicationFlags.FLAGS_NONE  # default = single instance
        )

    def do_activate(self):
        # Called on first launch AND on subsequent launch attempts
        # If wizard exists, present it; if already done, no-op or re-present tray
        if hasattr(self, "_wizard") and self._wizard:
            self._wizard.present()

app = App()
app.run(sys.argv)
```

### Pattern 2: Gtk.Stack Custom Wizard (Forward-Compatible)

**What:** `Gtk.Stack` with manual Back/Next/Finish buttons replaces deprecated `Gtk.Assistant`. Each page is a named child of the stack; navigation is driven by `stack.set_visible_child_name()`.

**When to use:** Multi-step wizard — the correct approach now that Gtk.Assistant is deprecated.

```python
# Source: https://pygobject.gnome.org/tutorials/gtk4/layout-widgets
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

class WizardWindow(Gtk.ApplicationWindow):
    PAGES = ["api_key", "microphone", "vocabulary"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs, title="Setup")
        self._current = 0

        self.stack = Gtk.Stack()
        self.stack.props.transition_type = Gtk.StackTransitionType.SLIDE_LEFT_RIGHT

        # Add pages
        self.stack.add_named(self._build_api_key_page(), "api_key")
        self.stack.add_named(self._build_microphone_page(), "microphone")
        self.stack.add_named(self._build_vocabulary_page(), "vocabulary")

        # Navigation buttons
        self.back_btn = Gtk.Button(label="Back")
        self.next_btn = Gtk.Button(label="Next")
        self.back_btn.connect("clicked", self._on_back)
        self.next_btn.connect("clicked", self._on_next)

        btn_box = Gtk.Box(spacing=6)
        btn_box.append(self.back_btn)
        btn_box.append(self.next_btn)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.append(self.stack)
        vbox.append(btn_box)
        self.set_child(vbox)
        self._update_nav()

    def _on_next(self, _btn):
        self._current = min(self._current + 1, len(self.PAGES) - 1)
        self.stack.set_visible_child_name(self.PAGES[self._current])
        self._update_nav()

    def _on_back(self, _btn):
        self._current = max(self._current - 1, 0)
        self.stack.set_visible_child_name(self.PAGES[self._current])
        self._update_nav()

    def _update_nav(self):
        self.back_btn.set_sensitive(self._current > 0)
        last = self._current == len(self.PAGES) - 1
        self.next_btn.set_label("Finish" if last else "Next")
```

### Pattern 3: Async API Validation with Spinner

**What:** Run Groq HTTP call in a `threading.Thread`; use `GLib.idle_add` to update UI. GTK is not thread-safe — all widget changes must happen on the main thread.

**When to use:** Any blocking I/O during the wizard flow (Groq validation).

```python
# Source: https://pygobject.gnome.org/guide/threading
import threading
import requests
from gi.repository import GLib, Gtk

class ApiKeyPage(Gtk.Box):
    def _on_validate(self, _btn):
        self.spinner.start()
        self.next_btn.set_sensitive(False)
        self.error_label.set_text("")
        key = self.entry.get_text().strip()
        thread = threading.Thread(target=self._validate_key, args=(key,), daemon=True)
        thread.start()

    def _validate_key(self, key):
        result = _check_groq_key(key)
        GLib.idle_add(self._on_validation_done, result)

    def _on_validation_done(self, result):
        self.spinner.stop()
        if result["ok"]:
            self.next_btn.set_sensitive(True)
        else:
            self.error_label.set_text(result["message"])
        return False  # GLib.idle_add callback must return False to run once
```

### Pattern 4: Groq API Key Validation

**What:** Two-pass validation — format check (prefix `gsk_`, minimum length), then live HTTP call.

```python
# Source: https://console.groq.com/docs/errors + https://docs.gitguardian.com/...
import requests

def _check_groq_key(api_key: str) -> dict:
    # Pass 1: format
    if not api_key.startswith("gsk_") or len(api_key) < 20:
        return {"ok": False, "message": "Invalid API key format"}

    # Pass 2: live call
    try:
        r = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if r.status_code == 200:
            return {"ok": True}
        elif r.status_code == 401:
            return {"ok": False, "message": "Invalid API key"}
        else:
            return {"ok": False, "message": f"Unexpected response ({r.status_code})"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "message": "Could not connect to Groq — check your internet connection"}
    except requests.exceptions.Timeout:
        return {"ok": False, "message": "Connection timed out — check your internet connection"}
```

### Pattern 5: Config Read/Write with 0600 Permissions

```python
# Source: Python stdlib docs
import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "linux-speech-flow"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "groq_api_key": "",
    "microphone": "",
    "vocabulary": [],
    "setup_complete": False,
}

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG.copy()
    with CONFIG_PATH.open() as f:
        return {**DEFAULT_CONFIG, **json.load(f)}

def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    os.chmod(CONFIG_PATH, 0o600)
```

### Pattern 6: PulseAudio/PipeWire Device Enumeration

**What:** `pulsectl.Pulse.source_list()` returns `PulseSourceInfo` objects with `name` (device ID) and `description` (human-readable label). Filter out monitor sources (they end in `.monitor` or have `description` containing "Monitor").

```python
# Source: https://github.com/mk-fg/python-pulse-control
import pulsectl

def list_microphones() -> list[dict]:
    with pulsectl.Pulse("linux-speech-flow") as pulse:
        sources = pulse.source_list()
    return [
        {"name": s.name, "description": s.description}
        for s in sources
        if not s.name.endswith(".monitor")
    ]
```

### Pattern 7: API key field masking

**What:** Use `Gtk.PasswordEntry` with `show_peek_icon=True` — built-in show/hide toggle, no manual implementation needed.

```python
# Source: https://pygobject.gnome.org/tutorials/gtk4/controls/entries
from gi.repository import Gtk

entry = Gtk.PasswordEntry()
entry.props.placeholder_text = "gsk_..."
entry.props.show_peek_icon = True  # adds eye icon toggle built-in
```

### Pattern 8: pyproject.toml with src layout

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "linux-speech-flow"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.31",
    "pulsectl>=24.0",
]

[project.scripts]
linux-speech-flow = "linux_speech_flow.app:main"

[tool.setuptools.packages.find]
where = ["src"]
```

### Anti-Patterns to Avoid

- **Using Gtk.Assistant:** Deprecated since GTK 4.10, removed in GTK 5. Use Gtk.Stack.
- **GTK calls from threads:** Always use `GLib.idle_add()` to schedule UI updates from worker threads. Direct widget access from threads will crash or corrupt state.
- **Lock file for single-instance:** Gtk.Application with `FLAGS_NONE` handles this natively via D-Bus. Lock files have race conditions and stale file edge cases.
- **Writing config before wizard completes:** Set `setup_complete: false` in config; only set `true` after Finish. Detect incomplete setup by checking this flag, not file existence.
- **Storing API key in env var:** User-facing app stores key in config.json (0600 permissions). Not in shell environment.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| API key visibility toggle | Custom Gtk.Entry + button | `Gtk.PasswordEntry(show_peek_icon=True)` | Built into GTK4 with correct UX patterns |
| Single-instance enforcement | fcntl lock files | `Gtk.Application(flags=FLAGS_NONE)` | D-Bus-based; handles stale locks, race conditions automatically |
| Audio device enumeration | subprocess + pactl + string parsing | `pulsectl.source_list()` | Structured API; pactl output format varies across distros |
| HTTP validation | Custom socket/urllib | `requests` library | Error handling, timeouts, TLS all handled correctly |
| XDG directory creation | Manual os.makedirs | `pathlib.Path.mkdir(parents=True, exist_ok=True)` | Atomic, handles race conditions |

**Key insight:** GTK4 has built-in solutions for most wizard UX patterns. The temptation to hand-roll (visibility toggles, progress indicators, page navigation) is rarely worth it.

## Common Pitfalls

### Pitfall 1: Gtk.Assistant Deprecation
**What goes wrong:** Code using `Gtk.Assistant` works today but will emit deprecation warnings and break on GTK 5 (target for Ubuntu 26.04+).
**Why it happens:** Gtk.Assistant was the obvious wizard widget; its replacement is not documented in Gtk.Assistant's own docs.
**How to avoid:** Use `Gtk.Stack` + manual navigation buttons from the start.
**Warning signs:** DeprecationWarning mentioning "Gtk.Assistant is deprecated since 4.10"

### Pitfall 2: GTK Widget Calls from Background Threads
**What goes wrong:** App crashes or hangs when updating spinner/labels from Groq validation thread.
**Why it happens:** GTK is not thread-safe; all widget access must be on the main thread.
**How to avoid:** All thread→UI communication goes through `GLib.idle_add(callback, args)`. The callback must `return False` to run once.
**Warning signs:** Random segfaults or "GLib-GObject-WARNING: invalid unclassed pointer" in stderr.

### Pitfall 3: pasimple Cannot Enumerate Devices
**What goes wrong:** Using pasimple (the locked-in audio library for Phase 2) to list microphones returns nothing.
**Why it happens:** pasimple wraps PulseAudio's "simple API" which provides no device enumeration — only stream playback/recording.
**How to avoid:** Use `pulsectl` (separate library) for device enumeration. pasimple is only for Phase 2 audio capture. Both can coexist.
**Warning signs:** No `list_sources()` or equivalent method on PaSimple objects.

### Pitfall 4: PyGObject Not Available in Standard venv
**What goes wrong:** `import gi` fails in a pip-created venv even though `python3-gi` is system-installed.
**Why it happens:** PyGObject installs into system Python, not venvs by default. PEP 668 also blocks pip from installing `PyGObject` system-wide on Ubuntu 24.04+.
**How to avoid:** Create venv with `python3 -m venv --system-site-packages .venv`. This allows access to system `gi` package. For `.deb` packaging: use dh-virtualenv or fpm with `--system-site-packages`.
**Warning signs:** `ModuleNotFoundError: No module named 'gi'` in venv.

### Pitfall 5: Config Written Before Wizard Completes
**What goes wrong:** User quits mid-wizard; partial config exists; next launch skips wizard because config file exists.
**Why it happens:** Checking for file existence rather than `setup_complete` flag.
**How to avoid:** Write partial config as user progresses (so validated key is preserved), but gate wizard display on `config.get("setup_complete", False)` being `False`.
**Warning signs:** User reports wizard never reappears after incomplete setup.

### Pitfall 6: pulsectl PipeWire Compatibility
**What goes wrong:** `pulsectl` fails to connect on systems with PipeWire but without `pipewire-pulse` bridge.
**Why it happens:** pulsectl uses `libpulse`; PipeWire's libpulse compatibility requires `pipewire-pulse` package.
**How to avoid:** Add `pipewire-pulse` as a Recommends dependency in packaging. Wrap `pulsectl.Pulse()` in try/except `pulsectl.PulseError` with fallback message.
**Warning signs:** `pulsectl.pulsectl.PulseError: Failed to connect to pulse` on PipeWire-only systems.

### Pitfall 7: Monitor Sources in Microphone List
**What goes wrong:** User sees "Monitor of Built-in Audio" in microphone dropdown — this is a loopback source, not a mic.
**Why it happens:** PulseAudio/PipeWire exposes monitor sources (playback loopbacks) in `source_list()` alongside real input devices.
**How to avoid:** Filter out sources where `name.endswith(".monitor")`. Some distros use different naming; also filter where `description` contains "Monitor of".
**Warning signs:** Users selecting a monitor source get no audio input during transcription.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gtk.Assistant for wizards | Gtk.Stack + manual nav buttons | GTK 4.10 (approx 2023) | Gtk.Assistant deprecated; must migrate |
| sounddevice for device listing | pulsectl for enumeration | Phase 0 decision | sounddevice (PortAudio 19.6) cannot enumerate PA/PW devices |
| setup.py + setup.cfg | pyproject.toml | PEP 517/518, 2023+ | setuptools>=61 reads pyproject.toml natively |
| system pip install | venv with --system-site-packages | Ubuntu 24.04 / PEP 668 | System pip blocked; venv required for non-PyGObject deps |

**Deprecated/outdated:**
- `Gtk.Assistant`: Deprecated GTK 4.10, removed in GTK 5. Do not use.
- `setup.py`: Still works but not recommended; pyproject.toml is standard.
- `sounddevice` for PA/PW device listing: PortAudio 19.6.0 cannot enumerate PA/PW sources — confirmed from prior decisions.

## Open Questions

1. **pulsectl PipeWire compatibility on Ubuntu 22.04**
   - What we know: pulsectl uses libpulse; PipeWire ships `pipewire-pulse` as compatibility layer; Ubuntu 22.04 ships both PA and PW depending on install path
   - What's unclear: Whether `pulsectl` works out of the box on Ubuntu 22.04 with PipeWire (no `pipewire-pulse` package found in search results for that distro version)
   - Recommendation: Test in Phase 1 integration step; wrap in try/except with clear error message; add `python3-pulsectl` or `libpulse0` to package dependencies

2. **Groq API key format stability**
   - What we know: Key prefix `gsk_` confirmed via GitGuardian detector documentation
   - What's unclear: Whether Groq will change key format; no official Groq docs confirm the prefix
   - Recommendation: Make format check lenient — only check `startswith("gsk_")` and minimum length (~50 chars). The live API call is the real gate; format check is just UX optimization.

3. **Settings window: reuse wizard pages or separate flat panel**
   - What we know: User said "Claude's discretion — choose simplest GTK implementation"
   - Recommendation: Reuse the same page widgets extracted into separate classes (ApiKeyPage, MicrophonePage, VocabularyPage), show them in a `Gtk.Notebook` or simple vertical layout in a Settings window. This avoids code duplication and wizard navigation complexity in Settings.

## Sources

### Primary (HIGH confidence)
- `/websites/pygobject_gnome` (Context7) — Gtk.Application, Gtk.Stack, Gtk.PasswordEntry, threading/GLib.idle_add patterns
- `/websites/api_pygobject_gnome` (Context7) — Gtk.Assistant deprecation signals confirmed
- https://docs.gtk.org/gtk4/class.Assistant.html — Deprecated since 4.10, removed in GTK 5 (fetched directly)
- https://console.groq.com/docs/errors — HTTP 401 error structure for invalid key (fetched directly)
- https://github.com/mk-fg/python-pulse-control — pulsectl source_list() API (fetched directly)

### Secondary (MEDIUM confidence)
- https://docs.gitguardian.com/secrets-detection/secrets-detection-engine/detectors/specifics/groq_api_key — Groq API key prefix `gsk_` (WebSearch → GitGuardian official docs)
- https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ — pyproject.toml src layout patterns (WebSearch → PyPA official)
- https://pygobject.gnome.org/guide/threading — GLib.idle_add threading pattern (Context7 + WebSearch convergence)

### Tertiary (LOW confidence)
- pulsectl PipeWire compatibility: noted in search results but not verified against pulsectl 24.12.0 changelog
- Groq `gsk_` key prefix: GitGuardian docs (authoritative for detection), but not from Groq's own documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PyGObject, GTK4, json/pathlib verified via system packages and Context7; pulsectl via GitHub README; requests widely known
- Architecture: HIGH — Gtk.Stack pattern from Context7; threading pattern from Context7; config from stdlib docs
- Pitfalls: HIGH (GTK.Assistant, threading) / MEDIUM (pulsectl PipeWire, monitor sources) — threading/deprecation from official docs; PipeWire from WebSearch

**Research date:** 2026-02-19
**Valid until:** 2026-05-19 (stable libraries; GTK4 deprecation status won't change before GTK5 release)
