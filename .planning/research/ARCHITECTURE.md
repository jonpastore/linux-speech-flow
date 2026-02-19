# Architecture Research

**Domain:** Python Linux system tray voice dictation application
**Researched:** 2026-02-18
**Confidence:** HIGH

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         GTK Main Thread                              │
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐     │
│  │  AppIndicator │     │  State       │     │  Clipboard/Paste │     │
│  │  System Tray  │◄───►│  Manager     │────►│  (xdotool/xclip) │     │
│  └──────────────┘     └──────┬───────┘     └──────────────────┘     │
│                              │                                       │
│         GLib.idle_add()  ▲   │   GLib.idle_add()  ▲                  │
│                          │   ▼                    │                   │
├──────────────────────────┼───┼────────────────────┼──────────────────┤
│                  Worker Threads                                       │
│                              │                                       │
│  ┌──────────────┐     ┌─────▼────────┐     ┌──────────────────┐     │
│  │  Hotkey       │────►│  Pipeline    │────►│  Groq API Client │     │
│  │  Listener     │     │  Coordinator │     │  (Whisper + LLM) │     │
│  │  (pynput)     │     └──────┬───────┘     └──────────────────┘     │
│  └──────────────┘            │                                       │
│                        ┌─────▼────────┐                              │
│                        │  Audio       │                              │
│                        │  Recorder    │                              │
│                        │  (sounddevice)│                              │
│                        └──────────────┘                              │
├──────────────────────────────────────────────────────────────────────┤
│                         Filesystem                                    │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────────────┐     │
│  │ Config   │     │ Cache        │     │ Data                 │     │
│  │ ~/.config│     │ ~/.cache     │     │ ~/.local/share       │     │
│  │ /freeflow│     │ /freeflow    │     │ /freeflow            │     │
│  └──────────┘     └──────────────┘     └──────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| AppIndicator System Tray | Menu bar icon, status display, menu actions (settings, quit) | `gi.repository.AppIndicator3` with `Gtk.Menu`, runs on GTK main thread |
| State Manager | Central state (recording, transcribing, error, config), notifies UI | Plain Python class with callback registration, thread-safe via `GLib.idle_add()` |
| Hotkey Listener | Global key press/release detection for push-to-talk | `pynput.keyboard.Listener` in its own daemon thread |
| Pipeline Coordinator | Orchestrates record->transcribe->post-process->paste sequence | Runs on a dedicated worker thread, uses `queue.Queue` for events |
| Audio Recorder | Captures microphone audio to WAV temp file | `sounddevice.InputStream` with callback writing to `queue.Queue`, `soundfile` for WAV |
| Groq API Client | HTTP calls to Groq Whisper and LLM endpoints | `requests` or `httpx` (sync, called from worker thread) |
| Clipboard/Paste | Inserts text at cursor in active application | `xclip` for clipboard + `xdotool key ctrl+v` via `subprocess` |
| Config | Persistent settings (API key, hotkey, vocabulary, mic) | JSON file at `~/.config/freeflow/config.json` |
| Cache | Temporary audio files | `~/.cache/freeflow/` with cleanup on startup |
| Data | Pipeline history, logs | `~/.local/share/freeflow/` |

## Recommended Project Structure

```
freeflow-linux/
├── src/
│   └── freeflow/
│       ├── __init__.py          # version string
│       ├── __main__.py          # entry point: parse args, start app
│       ├── app.py               # Application class: init components, run GTK main loop
│       ├── state.py             # StateManager: central state, observer callbacks
│       ├── tray.py              # TrayIcon: AppIndicator3 setup, menu construction
│       ├── hotkey.py            # HotkeyListener: pynput wrapper, key down/up events
│       ├── recorder.py          # AudioRecorder: sounddevice InputStream, WAV output
│       ├── pipeline.py          # PipelineCoordinator: record->transcribe->process->paste
│       ├── transcription.py     # GroqWhisperClient: API call to Groq Whisper
│       ├── postprocessing.py    # GroqLLMClient: API call to Groq LLM
│       ├── paste.py             # TextPaster: xclip + xdotool subprocess calls
│       ├── config.py            # ConfigManager: load/save JSON, XDG paths
│       └── constants.py         # XDG paths, API URLs, default settings
├── packaging/
│   └── debian/
│       ├── control              # package metadata, dependencies
│       ├── rules                # build rules
│       ├── changelog            # version history
│       ├── freeflow.desktop     # .desktop file for autostart
│       └── postinst             # post-install script
├── assets/
│   └── icons/                   # tray icons (idle, recording, processing)
├── pyproject.toml               # build config, dependencies, entry point
├── Makefile                     # build/install/package shortcuts
└── tests/
    ├── test_recorder.py
    ├── test_pipeline.py
    └── test_config.py
```

### Structure Rationale

- **src/freeflow/:** Single flat package. No sub-packages needed -- the app has ~10 modules total. Flat is better than nested for a project this size.
- **Each file = one component:** Mirrors the component boundary diagram above. Every module owns one concern and exposes a clean interface to the coordinator.
- **packaging/debian/:** Separated from source. Contains everything needed for `dpkg-buildpackage` or FPM.
- **assets/icons/:** Tray icon files referenced by AppIndicator3 (needs icon name resolvable by GTK icon theme or absolute path).

## Architectural Patterns

### Pattern 1: GTK Main Loop as the Event Loop

**What:** The GTK main loop (`Gtk.main()`) owns the main thread. All UI updates (tray icon, menu state) happen here. Worker threads communicate back to the main thread exclusively via `GLib.idle_add()`.

**When to use:** Always. This is not optional -- GTK is not thread-safe. Any GTK call from a non-main thread will cause segfaults or silent corruption.

**Trade-offs:** Simple, well-documented pattern. Requires discipline to never touch GTK objects from worker threads.

**Example:**
```python
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AppIndicator3

class App:
    def __init__(self):
        self.indicator = AppIndicator3.Indicator.new(
            "freeflow",
            "audio-input-microphone",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self._build_menu())

    def _build_menu(self):
        menu = Gtk.Menu()
        item_quit = Gtk.MenuItem(label="Quit")
        item_quit.connect("activate", self._on_quit)
        menu.append(item_quit)
        menu.show_all()
        return menu

    def _on_quit(self, _):
        Gtk.main_quit()

    def run(self):
        Gtk.main()
```

### Pattern 2: Queue-Based Thread Communication

**What:** Worker threads push events onto a `queue.Queue`. The pipeline coordinator reads from queues. State updates flow back to GTK via `GLib.idle_add()`. No shared mutable state between threads.

**When to use:** For all cross-thread communication: hotkey events, audio data, pipeline state transitions.

**Trade-offs:** Eliminates race conditions. Slightly more boilerplate than direct calls. The queue pattern is the same one used by sounddevice's own recording examples.

**Example:**
```python
import queue
import threading
from gi.repository import GLib

class PipelineCoordinator:
    def __init__(self, state_manager):
        self.event_queue = queue.Queue()
        self.state = state_manager
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def enqueue(self, event_type, data=None):
        self.event_queue.put((event_type, data))

    def _run(self):
        while True:
            event_type, data = self.event_queue.get()
            if event_type == "start_recording":
                self._handle_start_recording()
            elif event_type == "stop_recording":
                self._handle_stop_recording()
            elif event_type == "shutdown":
                break

    def _update_state(self, callback):
        GLib.idle_add(callback)
```

### Pattern 3: Callback-Based Audio Capture with sounddevice

**What:** `sounddevice.InputStream` runs its callback on a PortAudio thread. The callback copies audio chunks into a `queue.Queue`. A separate consumer writes chunks to a WAV file via `soundfile`. Recording starts/stops are controlled by opening/closing the stream context.

**When to use:** For all audio capture. This is the canonical sounddevice pattern from official documentation.

**Trade-offs:** Very low latency. The callback must be fast (just copy + enqueue). File I/O happens on the consumer side, not in the audio callback.

**Example:**
```python
import queue
import sounddevice as sd
import soundfile as sf
import tempfile

class AudioRecorder:
    def __init__(self, samplerate=16000, channels=1):
        self.samplerate = samplerate
        self.channels = channels
        self._queue = queue.Queue()
        self._stream = None
        self._file = None
        self._filepath = None

    def _callback(self, indata, frames, time, status):
        self._queue.put(indata.copy())

    def start(self):
        self._filepath = tempfile.mktemp(suffix='.wav',
                                          dir=cache_dir)
        self._file = sf.SoundFile(
            self._filepath, mode='x',
            samplerate=self.samplerate,
            channels=self.channels
        )
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            callback=self._callback
        )
        self._stream.start()
        self._drain_thread = threading.Thread(
            target=self._drain, daemon=True
        )
        self._drain_thread.start()

    def _drain(self):
        while self._stream and self._stream.active:
            try:
                data = self._queue.get(timeout=0.1)
                self._file.write(data)
            except queue.Empty:
                continue

    def stop(self):
        self._stream.stop()
        self._stream.close()
        self._stream = None
        while not self._queue.empty():
            self._file.write(self._queue.get())
        self._file.close()
        return self._filepath
```

### Pattern 4: pynput Listener as Daemon Thread

**What:** `pynput.keyboard.Listener` runs in its own daemon thread. The `on_press`/`on_release` callbacks fire on that thread. Callbacks must be fast -- they enqueue events to the pipeline coordinator rather than doing work directly.

**When to use:** For global hotkey detection. pynput uses X11/Xlib under the hood on X11, making it work system-wide without focus.

**Trade-offs:** Works without root on X11. On Wayland, may need `/dev/input` access (typically via `input` group). The listener thread starts before `Gtk.main()` and runs alongside it with no conflict.

**Example:**
```python
from pynput import keyboard

class HotkeyListener:
    def __init__(self, on_key_down, on_key_up, target_key=keyboard.Key.f5):
        self.target_key = target_key
        self._on_key_down = on_key_down
        self._on_key_up = on_key_up
        self._pressed = False
        self._listener = None

    def start(self):
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release
        )
        self._listener.daemon = True
        self._listener.start()

    def _handle_press(self, key):
        if key == self.target_key and not self._pressed:
            self._pressed = True
            self._on_key_down()

    def _handle_release(self, key):
        if key == self.target_key and self._pressed:
            self._pressed = False
            self._on_key_up()

    def stop(self):
        if self._listener:
            self._listener.stop()
```

## Data Flow

### Primary Pipeline Flow (Push-to-Talk)

```
[User holds hotkey]
    │
    ▼ (pynput listener thread)
[HotkeyListener.on_press]
    │
    ▼ (enqueue "start_recording")
[PipelineCoordinator._run]
    │
    ├──► GLib.idle_add(state.set_recording, True)  →  [Tray icon: recording]
    │
    ▼
[AudioRecorder.start()]
    │ (PortAudio callback thread)
    │ chunks → queue → drain thread → WAV file
    │
[User releases hotkey]
    │
    ▼ (pynput listener thread)
[HotkeyListener.on_release]
    │
    ▼ (enqueue "stop_recording")
[PipelineCoordinator._run]
    │
    ├──► GLib.idle_add(state.set_transcribing, True)  →  [Tray icon: processing]
    │
    ▼
[AudioRecorder.stop()] → returns /tmp/freeflow/recording.wav
    │
    ▼ (same worker thread)
[GroqWhisperClient.transcribe(wav_path)]
    │ HTTP POST multipart/form-data to api.groq.com
    │
    ▼ returns raw transcript string
[GroqLLMClient.post_process(transcript, context)]
    │ HTTP POST JSON to api.groq.com
    │
    ▼ returns cleaned transcript string
[TextPaster.paste(cleaned_text)]
    │ subprocess: xclip -selection clipboard <<< text
    │ subprocess: xdotool key ctrl+v
    │
    ├──► GLib.idle_add(state.set_idle)  →  [Tray icon: idle]
    │
    ▼
[Done]
```

### State Update Flow

```
[Worker Thread]
    │
    ▼
GLib.idle_add(state_manager.update, {"recording": True})
    │
    ▼ (GTK main thread, next idle cycle)
[StateManager.update()]
    │
    ├──► notify_observers("recording_changed")
    │       │
    │       ▼
    │   [TrayIcon._on_state_changed()]
    │       │
    │       ▼
    │   indicator.set_icon_full("freeflow-recording", "Recording")
    │   menu_item_status.set_label("Recording...")
    │
    ▼
[GTK renders updated tray]
```

### Key Data Flows

1. **Audio capture flow:** Microphone → PortAudio callback → `queue.Queue` → drain thread → WAV file on disk. The queue decouples the real-time audio callback from file I/O.

2. **Pipeline event flow:** pynput callback → `event_queue.put()` → PipelineCoordinator thread → sequential processing. Events are strictly ordered by the queue.

3. **UI update flow:** Worker thread → `GLib.idle_add(callback)` → GTK main thread executes callback → tray icon/menu updates. This is the only safe path to touch GTK objects.

4. **Config flow:** Config file on disk → `ConfigManager.load()` at startup → in-memory dict → `ConfigManager.save()` on change. No hot-reload needed; settings apply on next pipeline run.

## Threading Model (Concrete)

The application uses **4 threads** at steady state:

| Thread | Lifecycle | Owns | Blocked By |
|--------|-----------|------|------------|
| **Main (GTK)** | App start to quit | GTK main loop, AppIndicator, all UI | `Gtk.main()` event loop |
| **Hotkey Listener** | Daemon, started before `Gtk.main()` | pynput X11 event reading | X11 event select |
| **Pipeline Worker** | Daemon, started before `Gtk.main()` | Event queue processing, API calls | `queue.Queue.get()` |
| **Audio Drain** | Ephemeral, created per recording | WAV file writing from audio queue | `queue.Queue.get()` with timeout |

Additionally, **PortAudio** spawns its own internal thread for the audio callback during recording. This is managed by sounddevice and not directly controlled.

**Why not asyncio?** The GTK main loop and asyncio event loop compete for the main thread. Integrating them (via `gbulb` or manual loop nesting) adds complexity for no benefit in this app. The API calls are few (2 per pipeline run) and sequential. Blocking `requests` calls on the worker thread are simpler and sufficient.

**Why not a single worker thread for everything?** The hotkey listener must run continuously and independently. The pipeline worker blocks during API calls (1-3 seconds). If they shared a thread, hotkey events would be delayed during transcription. Separate threads with a queue keeps them decoupled.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Groq Whisper API | HTTP POST `multipart/form-data` to `/openai/v1/audio/transcriptions` | 16kHz mono WAV, model: `whisper-large-v3`. Timeout: 20s. |
| Groq LLM API | HTTP POST JSON to `/openai/v1/chat/completions` | Model: `llama-4-scout-17b-16e-instruct`. System prompt includes context. Timeout: 20s. |
| X11 (via pynput) | Xlib event monitoring for keyboard | Requires X11 display. Will not work on pure Wayland without `/dev/input` fallback. |
| xdotool | `subprocess.run(["xdotool", "key", "ctrl+v"])` | X11 only. For Wayland: `wtype` is the equivalent. |
| xclip | `subprocess.run(["xclip", "-selection", "clipboard"])` | X11 only. For Wayland: `wl-copy`. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| HotkeyListener -> PipelineCoordinator | `event_queue.put(("start_recording", None))` | Fire-and-forget. Listener never waits. |
| PipelineCoordinator -> AudioRecorder | Direct method calls (`start()`, `stop()`) | Both on worker thread. Recorder is owned by coordinator. |
| PipelineCoordinator -> GroqWhisperClient | Direct method call, returns string | Blocking HTTP. Called from worker thread. |
| PipelineCoordinator -> GroqLLMClient | Direct method call, returns string | Blocking HTTP. Called from worker thread. |
| PipelineCoordinator -> TextPaster | Direct method call | subprocess calls. Fast (<100ms). |
| PipelineCoordinator -> StateManager | `GLib.idle_add(state.update, {...})` | Thread-safe bridge to GTK thread. |
| StateManager -> TrayIcon | Observer callback (registered at init) | Runs on GTK main thread since `idle_add` dispatches there. |

## Scaling Considerations

This is a single-user desktop application. "Scaling" means handling edge cases gracefully:

| Concern | Approach |
|---------|----------|
| Long recordings (>5 min) | Stream to WAV file via queue; memory stays flat. Groq has file size limits (~25MB); warn user or split. |
| Rapid hotkey toggles | Pipeline coordinator ignores start if already recording. Queue serializes events naturally. |
| API failures | Retry once. On second failure, show error in tray menu and reset to idle. Don't block pipeline thread. |
| Multiple displays / X11 screens | xdotool handles this. pynput monitors all X11 keyboards by default. |
| Wayland migration | Biggest scaling concern. Entire paste/hotkey path needs Wayland alternatives. Isolate behind interfaces. |

### Wayland Readiness Priority

**Build for X11 first, isolate Wayland-sensitive code behind interfaces:**

| Component | X11 Tool | Wayland Equivalent | Interface |
|-----------|----------|-------------------|-----------|
| Global hotkeys | pynput (Xlib) | evdev or portal-based | `HotkeyListener` abstract base |
| Text paste | xdotool | wtype | `TextPaster.paste()` method |
| Clipboard | xclip | wl-copy | `TextPaster._set_clipboard()` method |

The `paste.py` and `hotkey.py` modules should detect X11 vs Wayland at startup and select the appropriate backend. This is the same pattern used by VOXD (ydotool) and OpenWhispr (XTest vs uinput).

## Anti-Patterns

### Anti-Pattern 1: Calling GTK from Worker Threads

**What people do:** Directly update tray icon or menu labels from the pipeline worker thread.
**Why it's wrong:** GTK is not thread-safe. This causes intermittent segfaults, corrupted rendering, or silent data races. It may appear to work during development and crash in production.
**Do this instead:** Always use `GLib.idle_add(callback, *args)` to schedule GTK updates from worker threads. Every single GTK call from a non-main thread must go through this path.

### Anti-Pattern 2: Blocking the GTK Main Thread

**What people do:** Make HTTP API calls or do file I/O on the GTK main thread.
**Why it's wrong:** The entire UI freezes. The tray icon becomes unresponsive. On GNOME, the shell may flag the app as unresponsive.
**Do this instead:** All blocking work (API calls, audio recording, file writes) happens on the pipeline worker thread. The GTK thread only handles UI events and state-driven rendering.

### Anti-Pattern 3: Shared Mutable State Between Threads

**What people do:** Have the pipeline worker and GTK thread both read/write the same Python dict or object attributes without synchronization.
**Why it's wrong:** Python's GIL protects against crashes but not logical races. You get stale reads, torn updates, and bugs that only reproduce under load.
**Do this instead:** Use the queue-based event pattern. Worker thread produces events. GTK thread consumes them via `GLib.idle_add()`. State transitions are always applied on a single thread (the GTK main thread).

### Anti-Pattern 4: Using asyncio with GTK

**What people do:** Try to run `asyncio.run()` or create an event loop alongside `Gtk.main()` for the API calls.
**Why it's wrong:** Two event loops competing for the main thread. `gbulb` exists but is poorly maintained and adds fragile complexity. For 2 HTTP calls per pipeline run, asyncio provides no benefit.
**Do this instead:** Use blocking `requests`/`httpx` calls on the worker thread. Simple, debuggable, sufficient.

### Anti-Pattern 5: Heavy Work in pynput Callbacks

**What people do:** Start audio recording or make API calls directly inside the `on_press`/`on_release` callback.
**Why it's wrong:** pynput callbacks run on the X11 event thread. Blocking this thread freezes keyboard input system-wide for all applications.
**Do this instead:** Callbacks should only `event_queue.put()` and return immediately. All real work happens on the pipeline coordinator thread.

## .deb Package Structure

```
freeflow_1.0.0-1_amd64.deb
├── DEBIAN/
│   ├── control                  # Package metadata, depends
│   ├── postinst                 # Post-install: desktop file registration
│   └── prerm                    # Pre-remove: cleanup
├── usr/
│   ├── bin/
│   │   └── freeflow             # Entry point script (or symlink)
│   ├── lib/python3/dist-packages/
│   │   └── freeflow/            # Python package
│   └── share/
│       ├── applications/
│       │   └── freeflow.desktop # .desktop launcher
│       ├── icons/hicolor/
│       │   └── scalable/apps/
│       │       └── freeflow.svg # App icon
│       └── freeflow/
│           └── icons/           # Tray status icons
└── etc/
    └── (nothing - all config is per-user in XDG dirs)
```

### pyproject.toml Entry Point

```toml
[project.scripts]
freeflow = "freeflow.__main__:main"
```

### Dependencies (DEBIAN/control)

```
Depends: python3 (>= 3.10),
         python3-gi,
         gir1.2-appindicator3-0.1,
         python3-sounddevice | python3-pip,
         libportaudio2,
         xdotool,
         xclip
Recommends: gnome-shell-extension-appindicator
```

## XDG Directory Conventions

| Directory | XDG Variable | Default | FreeFlow Usage |
|-----------|-------------|---------|----------------|
| Config | `$XDG_CONFIG_HOME` | `~/.config` | `~/.config/freeflow/config.json` (API key, hotkey, vocabulary) |
| Cache | `$XDG_CACHE_HOME` | `~/.cache` | `~/.cache/freeflow/` (temp WAV files, cleaned on startup) |
| Data | `$XDG_DATA_HOME` | `~/.local/share` | `~/.local/share/freeflow/` (pipeline history log) |
| State | `$XDG_STATE_HOME` | `~/.local/state` | `~/.local/state/freeflow/` (log files) |

Use `xdg-base-dirs` Python library to resolve these paths. It respects environment variable overrides and returns `pathlib.Path` objects.

```python
from xdg_base_dirs import xdg_config_home, xdg_cache_home, xdg_data_home

CONFIG_DIR = xdg_config_home() / "freeflow"
CACHE_DIR = xdg_cache_home() / "freeflow"
DATA_DIR = xdg_data_home() / "freeflow"
```

## Build Order (Dependency-Driven)

The components should be built in this order, where each phase produces a testable artifact:

```
Phase 1: config.py + constants.py
    │     (XDG paths, JSON config load/save)
    │     Testable: config round-trips, paths resolve
    │
Phase 2: recorder.py
    │     (sounddevice InputStream + WAV output)
    │     Testable: record 3s audio, verify WAV file
    │     Depends on: config (cache dir for temp files)
    │
Phase 3: transcription.py + postprocessing.py
    │     (Groq API clients)
    │     Testable: transcribe a test WAV, post-process text
    │     Depends on: config (API key)
    │
Phase 4: paste.py
    │     (xclip + xdotool)
    │     Testable: paste text into a text editor
    │     Depends on: nothing (standalone subprocess calls)
    │
Phase 5: hotkey.py
    │     (pynput listener)
    │     Testable: detect key press/release, print events
    │     Depends on: nothing (standalone)
    │
Phase 6: pipeline.py + state.py
    │     (coordinator wiring all components together)
    │     Testable: hold key → record → transcribe → paste end-to-end
    │     Depends on: all above
    │
Phase 7: tray.py + app.py
    │     (AppIndicator3 UI, GTK main loop, menu)
    │     Testable: tray icon appears, menu works, state reflected
    │     Depends on: state.py, pipeline.py
    │
Phase 8: packaging
          (.deb, .desktop file, icon installation)
          Testable: install .deb on clean system, app runs
          Depends on: all above
```

**Rationale:** Each phase can be tested independently with a simple script. The pipeline coordinator (Phase 6) is the integration point -- it can initially be tested from a CLI script without any GTK. The tray UI (Phase 7) is pure presentation layered on top. This order lets you validate the core pipeline before adding UI complexity.

## Sources

- [PyGObject Threading Guide](https://pygobject.gnome.org/guide/threading.html) -- official GTK threading rules (HIGH confidence)
- [pynput Keyboard Documentation](https://pynput.readthedocs.io/en/latest/keyboard.html) -- listener threading model (HIGH confidence)
- [pystray Documentation](https://pystray.readthedocs.io/en/latest/usage.html) -- system tray patterns, X11 limitations (HIGH confidence)
- [python-sounddevice Examples](https://python-sounddevice.readthedocs.io/en/0.4.0/examples.html) -- callback recording pattern (HIGH confidence)
- [AppIndicator3 Minimal Example](https://gist.github.com/candidtim/c943835a9742f5021eeb) -- AppIndicator setup pattern (MEDIUM confidence)
- [GLib Main Event Loop](https://docs.gtk.org/glib/main-loop.html) -- GLib.idle_add thread safety (HIGH confidence)
- [xdg-base-dirs on PyPI](https://pypi.org/project/xdg-base-dirs/) -- XDG path resolution (HIGH confidence)
- [XDG Base Directory - ArchWiki](https://wiki.archlinux.org/title/XDG_Base_Directory) -- directory conventions (HIGH confidence)
- [VOXD GitHub](https://github.com/jakovius/voxd) -- reference Linux voice dictation architecture (MEDIUM confidence)
- [Push-to-Talk GitHub](https://github.com/yixin0829/push-to-talk) -- reference push-to-talk architecture (MEDIUM confidence)
- [OpenWhispr GitHub](https://github.com/openwhispr/openwhispr) -- paste mechanism patterns, terminal detection (MEDIUM confidence)
- [Debian Python Packaging Tools](https://people.debian.org/~stefanor/python-policy-sphinx/packaging-tools.html) -- dh-python packaging (MEDIUM confidence)

---
*Architecture research for: Python Linux system tray voice dictation application*
*Researched: 2026-02-18*
