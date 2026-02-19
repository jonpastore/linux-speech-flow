# Stack Research

**Domain:** Linux system tray voice dictation app (Python, X11)
**Researched:** 2026-02-18
**Confidence:** MEDIUM-HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Runtime | 3.11 is default on Ubuntu 24.04/Pop!_OS. 3.12+ also works. Avoid 3.13 until ecosystem catches up. |
| sounddevice | 0.5.5 | Audio capture (mic recording) | Pythonic PortAudio wrapper with clean stream/callback API. Simpler than PyAudio for record-to-buffer workflows. Handles WAV writing with scipy or manual numpy. |
| pynput | 1.8.1 | Global hotkey detection (key down/up) | Provides `on_press`/`on_release` callbacks for global key monitoring on X11 via Xlib. Supports hold-to-record pattern needed for F9. No GTK dependency. |
| groq | 1.0.0 | Groq API client (Whisper + LLM) | Official Python SDK. OpenAI-compatible. Handles multipart upload for audio transcription and chat completions for post-processing. |
| AppIndicator3 (via PyGObject) | GTK 3.0 / gi | System tray icon | The *only* reliable way to show a tray icon on modern GNOME. pystray uses AppIndicator3 as its Linux backend anyway. Going direct avoids an abstraction layer and gives full control over menu updates and icon state. |
| python-xlib | 0.33 | Active window name, X11 queries | Get `_NET_ACTIVE_WINDOW` and `_NET_WM_NAME` properties. Lightweight, no GTK dependency. Used for context capture (what app user is dictating into). |
| Pillow | 12.1.1 | Screenshot capture | `ImageGrab.grab()` works on X11 (Linux support since Pillow 7.1). Can capture full screen or specific regions. Also used for screenshot compression before sending to Groq vision API. |
| keyring | 25.7.0 | Secure API key storage | Wraps D-Bus Secret Service (GNOME Keyring / KWallet). No plaintext config files for the Groq API key. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | 2.4.2 | Audio buffer handling | Required by sounddevice for array-based recording. Used to compute RMS audio levels for visual feedback. |
| scipy | (latest) | WAV file writing | `scipy.io.wavfile.write()` for saving recorded audio to WAV before Groq upload. Alternative: use `wave` stdlib module (zero deps). |
| ewmh (pyewmh) | 0.1.6 | EWMH window manager queries | Higher-level wrapper over python-xlib for `getActiveWindow()`. Use if you want cleaner code than raw Xlib property queries. Optional -- can do the same with python-xlib directly. |
| requests | (latest) | HTTP fallback | Only if groq SDK has issues. The macOS app uses raw URLSession/HTTP; groq SDK wraps httpx. Probably not needed. |

### System Dependencies (apt packages)

| Package | Purpose | Notes |
|---------|---------|-------|
| `gir1.2-appindicator3-0.1` | AppIndicator3 GObject introspection bindings | Required for system tray on GNOME/Ubuntu. GNOME needs the "AppIndicator and KStatusNotifierItem Support" shell extension (pre-installed on Pop!_OS/Ubuntu). |
| `gir1.2-gtk-3.0` | GTK3 GObject introspection | Required by AppIndicator3 and for menu construction. |
| `libportaudio2` | PortAudio shared library | Required by sounddevice. **CRITICAL**: Ubuntu 22.04/24.04 ships PortAudio 19.6.0 which lacks native PipeWire support. However, it works through PipeWire's PulseAudio compatibility layer (pipewire-pulse), which is the default on Pop!_OS 22.04+. |
| `xdotool` | Text injection + keyboard simulation | Used via subprocess to paste transcribed text: `xdotool key ctrl+v` after setting clipboard, or `xdotool type --clearmodifiers` for direct typing. |
| `xclip` | Clipboard management | Set clipboard contents before pasting: `xclip -selection clipboard`. Used in the clipboard+paste text injection strategy. |
| `scrot` | Screenshot backend for Pillow | Pillow's `ImageGrab` on Linux uses scrot if available. Improves screenshot reliability. |
| `libgirepository1.0-dev` | GObject Introspection development files | Needed to build PyGObject from pip if not using system package. |
| `python3-gi` | PyGObject system package | Alternative to pip-installing PyGObject. Easier to get working since it avoids compiling C extensions. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` | Python project/dependency management | Fast, modern replacement for pip/venv. Use `uv init`, `uv add`, `uv run`. Handles lockfiles and virtual environments. |
| `fpm` 1.17.0 | .deb package creation | Ruby-based tool. `fpm -s dir -t deb` packages a directory tree into a .deb. Avoids the complexity of dpkg-buildpackage/stdeb. Most practical for non-Debian-maintainer workflows. |
| `ruff` | Linting + formatting | Single tool replaces flake8, black, isort. Fast, opinionated. |
| `pytest` | Testing | Standard Python testing. |
| `pyproject.toml` | Project metadata | PEP 621 standard. Single source of truth for project config. Use `setuptools` or `hatchling` as build backend. |

## Installation

```bash
# System dependencies (Ubuntu/Pop!_OS)
sudo apt install -y \
    python3-gi \
    gir1.2-appindicator3-0.1 \
    gir1.2-gtk-3.0 \
    libportaudio2 \
    xdotool \
    xclip \
    scrot \
    python3-dev \
    libgirepository1.0-dev

# Python dependencies (via uv or pip)
pip install sounddevice numpy groq pynput python-xlib Pillow keyring

# Development dependencies
pip install ruff pytest

# For .deb packaging (one-time setup)
sudo apt install ruby-dev build-essential
sudo gem install fpm
```

## Text Injection Strategy

The macOS app uses `CGEvent` to simulate Cmd+V paste. On Linux X11, the equivalent is:

**Recommended: Clipboard + xdotool paste** (matches macOS behavior)
```bash
# 1. Set clipboard via xclip
echo -n "transcribed text" | xclip -selection clipboard
# 2. Simulate Ctrl+V via xdotool
xdotool key --clearmodifiers ctrl+v
```

**Fallback: xdotool type** (for apps that block paste)
```bash
xdotool type --clearmodifiers --delay 10 "transcribed text"
```

Both invoked via Python `subprocess.run()`. No Python wrapper library needed -- subprocess is simpler and avoids an abstraction layer over a CLI tool.

**Why not python-xdotool or other wrappers:** They are unmaintained wrappers around the CLI tool. Direct subprocess calls give full control and are trivially debuggable.

## Active Window + Screenshot Strategy

**Active window name** (for context capture):
```python
from Xlib import X, display
from Xlib.protocol import rq

d = display.Display()
root = d.screen().root
atom = d.intern_atom('_NET_ACTIVE_WINDOW')
window_id = root.get_full_property(atom, X.AnyPropertyType).value[0]
window = d.create_resource_object('window', window_id)
name = window.get_full_property(d.intern_atom('_NET_WM_NAME'), 0)
# Returns UTF-8 window title
```

**Screenshot** (for Groq vision context):
```python
from PIL import ImageGrab
screenshot = ImageGrab.grab()  # Full screen on X11
# Or for active window: use xdotool to get geometry, then grab(bbox=...)
```

## Secure API Key Storage

```python
import keyring
# Store
keyring.set_password("freeflow", "groq_api_key", api_key)
# Retrieve
api_key = keyring.get_password("freeflow", "groq_api_key")
```

Uses GNOME Keyring (via D-Bus Secret Service) on GNOME/Pop!_OS, KWallet on KDE. Falls back to encrypted file if neither available.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| sounddevice | PyAudio | If you need lower-level PortAudio control. PyAudio's API is more verbose and less Pythonic. sounddevice wraps the same PortAudio underneath. |
| sounddevice | pipewire_python | If you want native PipeWire (no PortAudio). Immature library, not widely used. Not recommended for v1. |
| pynput | keybinder3 (via gi) | If you only need GTK apps and want GTK-native hotkeys. Requires GTK main loop. pynput is standalone and works outside GTK. |
| pynput | python-xlib (raw) | If you want zero dependencies beyond Xlib. More code to write. pynput's Listener abstraction is cleaner. |
| AppIndicator3 (direct) | pystray | If you want cross-platform tray code. pystray uses AppIndicator3 on Linux anyway, adding an abstraction layer with some unsupported features (no default menu action). Going direct gives full control. |
| python-xlib | ewmh (pyewmh) | If you want a cleaner API for EWMH queries. ewmh wraps python-xlib. Either works; python-xlib is sufficient for our needs (active window name only). |
| fpm | stdeb | If you want Debian-policy-compliant packages. stdeb is broken on newer Debian/Ubuntu (trixie). fpm is simpler and works. |
| fpm | dpkg-buildpackage | If you are a Debian maintainer. Requires writing debian/ directory structure. Overkill for app distribution. |
| fpm | Nuitka + deb | If you want compiled Python (faster startup, harder to reverse-engineer). Adds C compiler dependency to build. Consider for v2. |
| keyring | plaintext config | Never for API keys. keyring uses OS-level encryption (GNOME Keyring / KWallet). |
| subprocess (xdotool) | python-xdotool | Don't. Unmaintained wrapper. subprocess.run() is more reliable and transparent. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PyAudio | More verbose API, no real advantage over sounddevice for recording. Both use PortAudio. Installation can be painful (needs portaudio19-dev to compile). | sounddevice (pip wheel, no compilation) |
| pystray | Adds abstraction over AppIndicator3 with no benefit on Linux-only app. Some features unsupported on Linux (menu default action). Last release Sep 2023. | AppIndicator3 directly via PyGObject |
| Wayland support (v1) | Wayland breaks global hotkeys (no `XGrabKey` equivalent), xdotool, xclip, Pillow ImageGrab, and python-xlib. The entire X11 ecosystem we need does not work on Wayland. | Target X11 only for v1. Wayland requires completely different tools (wtype, wl-clipboard, grim, libei). V2 consideration. |
| tkinter for tray | tkinter cannot create proper system tray indicators on Linux. It can only create windows, not tray icons. | AppIndicator3 |
| QSystemTrayIcon (Qt) | Pulls in entire Qt framework dependency (~100MB+). Overkill when GTK is already the desktop toolkit on target distros. | AppIndicator3 (GTK-native) |
| GSettings/dconf for API key | Not encrypted. API keys would be stored in plaintext in dconf database. | keyring (encrypted via GNOME Keyring) |
| python-dotenv for API key | .env files are plaintext on disk. Unacceptable for API credentials. | keyring for storage; env var override for CI/testing |

## Stack Patterns by Variant

**If targeting Ubuntu 24.04+ / Pop!_OS 24.04+ only:**
- PipeWire is default audio server
- PortAudio works through pipewire-pulse compatibility layer
- libportaudio2 from apt is sufficient (19.6.0 talks to PulseAudio API, PipeWire intercepts)
- No special audio configuration needed

**If also targeting Ubuntu 22.04 / Pop!_OS 22.04:**
- PipeWire is default on Pop!_OS 22.04 but NOT on stock Ubuntu 22.04 (which uses PulseAudio)
- PortAudio works with both PulseAudio and PipeWire-via-PulseAudio
- Same code works on both -- PortAudio talks PulseAudio protocol regardless

**If user has no desktop environment (headless / window manager only):**
- AppIndicator3 requires a system tray implementation (most WMs have one)
- xdotool works on any X11 setup
- No special handling needed, but document that a system tray is required

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| sounddevice 0.5.5 | numpy >= 1.0, libportaudio2 (any) | numpy is optional but recommended. System libportaudio2 from apt works on Ubuntu 22.04/24.04. |
| pynput 1.8.1 | python-xlib 0.33 | pynput uses Xlib internally on Linux. No conflict with our direct python-xlib usage -- they use separate Display connections. |
| groq 1.0.0 | Python >= 3.9 | Uses httpx internally. No conflicts with other libraries. |
| Pillow 12.1.1 | scrot (system) | Pillow's ImageGrab on Linux detects and uses scrot if installed. Falls back to gnome-screenshot or other tools. |
| keyring 25.7.0 | secretstorage (auto-installed) | On Linux, keyring automatically uses SecretStorage backend (D-Bus Secret Service). Requires a running GNOME Keyring or KWallet daemon. |
| AppIndicator3 | gir1.2-appindicator3-0.1 (apt) | Must install system GObject Introspection package. Cannot be pip-installed. |
| PyGObject (gi) | python3-gi (apt) | Install from apt, not pip, to avoid compilation issues. pip install PyGObject requires libgirepository1.0-dev and gcc. |

## GNOME System Tray: The Full Picture

This deserves special attention because GNOME removed the legacy system tray in GNOME Shell 3.26.

**How it works on target distros:**

1. **Pop!_OS** ships with the "AppIndicator and KStatusNotifierItem Support" GNOME Shell extension **pre-installed and enabled**. AppIndicator3 icons appear in the top bar automatically.

2. **Ubuntu** also ships with this extension pre-installed since Ubuntu 20.04.

3. **KDE/XFCE** have native system tray support. AppIndicator3 works on KDE via StatusNotifierItem protocol. XFCE has a system tray panel plugin.

**What our app needs to do:**
- Use `gi.repository.AppIndicator3` to create an indicator
- Set `ACTIVE` status and attach a `Gtk.Menu`
- Provide an SVG or PNG icon (use absolute path)
- The icon changes state to reflect: idle, recording, transcribing

**Confidence: HIGH** -- This is the standard approach used by Slack, Discord, Dropbox, and other tray apps on Linux.

## .deb Packaging Strategy

**Use fpm** to create the .deb from a directory tree:

```bash
# 1. Build a directory tree that mirrors installed layout
mkdir -p build/usr/lib/freeflow
mkdir -p build/usr/bin
mkdir -p build/usr/share/applications
mkdir -p build/usr/share/icons/hicolor/scalable/apps

# 2. Copy Python venv or bundled app into build/usr/lib/freeflow/
# 3. Create launcher script in build/usr/bin/freeflow
# 4. Copy .desktop file and icon

# 5. Package with fpm
fpm -s dir -t deb \
    -n freeflow \
    -v 1.0.0 \
    --description "Voice dictation for Linux" \
    --url "https://github.com/user/freeflow-linux" \
    --license MIT \
    --depends python3 \
    --depends python3-gi \
    --depends gir1.2-appindicator3-0.1 \
    --depends libportaudio2 \
    --depends xdotool \
    --depends xclip \
    --after-install scripts/postinst.sh \
    -C build .
```

**Why fpm over stdeb:** stdeb requires setup.py (deprecated pattern), is broken on Debian trixie/newer Ubuntu, and limits you to packages available in apt repos. fpm works with any directory tree and handles dependencies declaratively.

**Why fpm over Nuitka/PyInstaller + deb:** For v1, shipping a Python virtualenv in the .deb is simpler and more debuggable. Compiled binaries (Nuitka) add build complexity. Consider for v2 if startup time or package size becomes an issue.

## systemd User Service

For auto-start on login (equivalent to macOS `SMAppService.mainApp.register()`):

```ini
# ~/.config/systemd/user/freeflow.service
[Unit]
Description=FreeFlow Voice Dictation
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/freeflow
Restart=on-failure
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
```

Enable with: `systemctl --user enable --now freeflow.service`

Alternatively, use a `.desktop` file in `~/.config/autostart/` (simpler, more conventional for GUI apps):

```ini
# ~/.config/autostart/freeflow.desktop
[Desktop Entry]
Type=Application
Name=FreeFlow
Exec=/usr/bin/freeflow
Icon=freeflow
X-GNOME-Autostart-enabled=true
```

**Recommendation:** Use `.desktop` autostart for v1 (simpler, user-visible in GNOME Tweaks). Offer systemd service as optional for power users.

## Sources

- [sounddevice PyPI](https://pypi.org/project/sounddevice/) -- version 0.5.5 confirmed, released 2026-01-23 (HIGH confidence)
- [sounddevice installation docs](https://python-sounddevice.readthedocs.io/en/latest/installation.html) -- Linux requires system libportaudio2 (HIGH confidence)
- [PortAudio PipeWire issue #425](https://github.com/PortAudio/portaudio/issues/425) -- PortAudio 19.6.0 (Ubuntu default) lacks native PipeWire, works through pipewire-pulse (MEDIUM confidence)
- [pynput PyPI](https://pypi.org/project/pynput/) -- version 1.8.1 confirmed, released 2025-03-17 (HIGH confidence)
- [pynput keyboard docs](https://pynput.readthedocs.io/en/latest/keyboard.html) -- on_press/on_release, GlobalHotKeys (HIGH confidence)
- [groq PyPI](https://pypi.org/project/groq/) -- version 1.0.0 confirmed, released 2025-12-17 (HIGH confidence)
- [Groq speech-to-text docs](https://console.groq.com/docs/speech-to-text) -- whisper-large-v3, whisper-large-v3-turbo models (HIGH confidence)
- [Pillow PyPI](https://pypi.org/project/Pillow/) -- version 12.1.1 confirmed, released 2026-02-11 (HIGH confidence)
- [python-xlib PyPI](https://pypi.org/project/python-xlib/) -- version 0.33, released 2022-12-25. Mature/stable. (HIGH confidence)
- [keyring PyPI](https://pypi.org/project/keyring/) -- version 25.7.0 confirmed, released 2025-11-16 (HIGH confidence)
- [pystray PyPI](https://pypi.org/project/pystray/) -- version 0.19.5, released 2023-09-17. Uses AppIndicator3 backend on Linux. (HIGH confidence)
- [GNOME AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/) -- required for GNOME Shell tray support (HIGH confidence)
- [Pop!_OS 22.04 release blog](https://blog.system76.com/popos-2204-lts-has-landed/) -- PipeWire is default audio server (HIGH confidence)
- [fpm docs](https://fpm.readthedocs.io/en/latest/) -- version 1.17.0, supports python-to-deb and dir-to-deb (MEDIUM confidence)
- [stdeb PyPI](https://pypi.org/project/stdeb/) -- version 0.11.0, broken on newer Debian (MEDIUM confidence)
- [pyewmh docs](https://ewmh.readthedocs.io/en/latest/ewmh.html) -- version 0.1.6, EWMH wrapper over Xlib (MEDIUM confidence)
- [numpy PyPI](https://pypi.org/project/numpy/) -- version 2.4.2 confirmed, requires Python 3.11+ (HIGH confidence)
- [xdotool paste patterns](https://sick.codes/paste-clipboard-linux-xdotool-ctrl-v-terminal-type/) -- clipboard + Ctrl+V strategy (MEDIUM confidence)
- [OpenWhispr](https://github.com/HeroTools/open-whispr) -- competitor: voice dictation with Whisper, similar concept (LOW confidence)
- [Vocalinux](https://vocalinux.com/) -- competitor: offline voice dictation for Linux (LOW confidence)
- [nerd-dictation](https://github.com/ideasman42/nerd-dictation) -- competitor: offline VOSK-based dictation (MEDIUM confidence)

---
*Stack research for: FreeFlow Linux -- Python voice dictation system tray app*
*Researched: 2026-02-18*
