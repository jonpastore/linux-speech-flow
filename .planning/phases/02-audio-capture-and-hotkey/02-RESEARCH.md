# Phase 2: Audio Capture & Hotkey - Research

**Researched:** 2026-02-19
**Domain:** X11 global hotkey (pynput), pasimple audio recording, WAV generation, paplay feedback, libnotify, RMS silence detection
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Area 1: F9 Hold Behavior**
- Brief tap (< 300ms): Ignore silently. No recording started, no feedback. Threshold: 300ms minimum hold before recording begins.
- Cancel: Escape key cancels an in-progress recording. On cancel: stop recording immediately, discard the partial WAV, do not pass to transcription. Play the normal stop sound (same as a regular stop — confirms recording ended).
- Max duration: 300 seconds default. User-configurable in Settings → Audio section. When max is hit: auto-stop recording and produce WAV for transcription (not an error condition — treat as normal stop).
- Silence auto-stop: If RMS stays below threshold for N consecutive seconds → auto-stop recording and produce WAV. Default: 10 seconds of silence triggers stop. N is configurable in Settings → Audio section. Silence threshold (RMS level) is a fixed implementation constant — only the duration is user-configurable.
- Key held at startup: Ignore. App only responds to fresh key-down events detected after startup.

**Area 2: Audio Feedback Sounds**
- Source: Bundled audio files shipped with the package. Style: soft chime / notification (not harsh beeps).
- Events covered: Recording start → soft chime up / ascending tone; Recording stop (normal) → soft chime down / descending tone; Error (mic unavailable, mid-record failure) → error sound distinct from start/stop.
- Generation: Create WAV files programmatically using Python's `wave` module during development (sine wave with fade-in/out). Store in `src/linux_speech_flow/sounds/` and include as package data in `pyproject.toml`.
- Playback: Use `paplay` (PulseAudio/PipeWire) for non-blocking sound playback. Target the user-configured output sink.
- Output device: User-configurable in Settings → Audio section (ComboBoxText of PulseAudio/PipeWire sinks, i.e., output devices — not input sources). Separate from the microphone (input) device. Default: system default sink.
- On/off toggle: Global sounds on/off toggle in Settings → Audio section. When off, no sounds play for any event (start, stop, error).

**Area 3: Error Handling UX**
- Mic unavailable when F9 pressed: Play error sound (if sounds enabled) + send desktop notification (libnotify) with message: "Microphone unavailable — check Settings". Do not enter recording state.
- Mic disappears mid-recording (e.g., USB unplugged): Stop recording immediately. Play error sound + send desktop notification. Discard partial WAV — do not pass to transcription.
- Visual indicator during recording: Send a desktop notification (libnotify) when recording starts: "Recording...". Phase 2 leaves this notification open. Phase 3 replaces it with "Transcribing..." using `notify-send --replace-id` when transcription begins. This notification chain (Recording → Transcribing → Done) spans Phase 2 and 3. This is the Phase 2 recording state indicator; Phase 4 will add tray icon state changes.

**Area 4: WAV File Lifecycle**
- Location: Python `tempfile.NamedTemporaryFile` in system `/tmp`. File is created before recording starts, written to during recording.
- Format: 16kHz, mono, s16le (signed 16-bit little-endian). This is the optimal format for Groq Whisper — no conversion needed before API upload in Phase 3.
- Cleanup: Phase 2 produces the WAV and passes the path. Phase 3 deletes the file immediately after transcription succeeds. On recording error or cancel: delete immediately in Phase 2.

**Area 5: Settings Window Changes (Phase 2 additions)**
- Add an "Audio" section to the existing `SettingsWindow` (settings.py) below the Microphone section.
- Fields:
  - Sounds on/off | Toggle switch | Default: On | Config key: `sounds_enabled`
  - Sound output device | ComboBoxText (PulseAudio sinks) | Default: System default | Config key: `sounds_output_device`
  - Max recording duration (sec) | SpinButton (1–600) | Default: 300 | Config key: `max_recording_duration`
  - Silence auto-stop duration (sec) | SpinButton (1–60) | Default: 10 | Config key: `silence_stop_duration`
- Config keys added to `~/.config/linux-speech-flow/config.json` schema. Default values must be applied when keys are absent (backward-compatible with Phase 1 configs).

### Claude's Discretion

No discretion areas documented in CONTEXT.md — all areas have locked decisions.

### Deferred Ideas (OUT OF SCOPE)

- Hotkey configurability (remapping F9 to a different key) — Phase 6 or later
- Per-recording volume normalization — post-Phase 3 concern
- Visual waveform display during recording — deferred to Phase 4 or later
- Silence threshold (RMS level) as a user-configurable field — fixed constant in implementation
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CORE-01 | Hold F9 to record audio, release to transcribe and paste | pynput 1.8.1 Listener with on_press/on_release callbacks; 300ms debounce via time.time(); GLib.idle_add for GTK thread safety |
| CORE-02 | Audio captured via PulseAudio/PipeWire | pasimple 0.0.3 PaSimple(PA_STREAM_RECORD, PA_SAMPLE_S16LE, 1, 16000, device_name=...) in a daemon thread; chunked blocking reads with stop Event |
| CORE-03 | WAV format ready for Groq Whisper (16kHz mono s16le) | WAV header written via Python `wave` module; tempfile.NamedTemporaryFile(suffix='.wav', delete=False) in /tmp |
| CORE-04 | Post-processing via Groq LLM | Phase 3 concern; WAV file path passed as return value from recording |
| CORE-05 | Text injected into focused application | Phase 3 concern; no Phase 2 work required |
</phase_requirements>

## Summary

Phase 2 introduces three independent subsystems that must cooperate: (1) a global X11 hotkey listener detecting F9 press/release, (2) a PulseAudio audio capture loop writing 16kHz mono s16le PCM to a WAV temp file, and (3) UI feedback via paplay sounds and notify-send desktop notifications.

The critical architectural decision is threading. pynput's `Listener` runs in its own daemon thread and fires callbacks there — all GTK operations (showing notifications, updating settings UI) must be marshalled to the GTK main thread via `GLib.idle_add()`. The audio recording loop must also run in a dedicated daemon thread because `pasimple.PaSimple.read()` blocks. The recording thread uses a `threading.Event` to stop cleanly; since `read()` blocks per-chunk, the thread wakes naturally at each chunk boundary to check the stop event. The main GTK thread never blocks.

The pasimple library (v0.0.3, January 2024, feature-complete) is confirmed to support device selection via `device_name` parameter, PA_SAMPLE_S16LE format, and 16kHz sample rate — matching Groq Whisper's optimal input format exactly. pynput 1.8.1 (March 2025) `Listener` supports separate on_press/on_release callbacks on X11, which is the correct API for push-to-talk (GlobalHotKeys does NOT support on_release). The `notify-send -p` flag prints the notification ID to stdout, enabling Phase 3 to replace "Recording..." with "Transcribing..." using `notify-send -r <id>`.

**Primary recommendation:** pynput Listener (not GlobalHotKeys) for F9 hold/release + pasimple PaSimple in a daemon thread for recording + subprocess.Popen(paplay) for non-blocking sound + subprocess.run(notify-send -p) for notifications.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pynput | 1.8.1 | Global X11 keyboard listener (F9 press/release) | Active (March 2025); threading.Thread-based listener; supports on_press + on_release separately; works on X11 without root |
| pasimple | 0.0.3 | PulseAudio/PipeWire audio recording from specific device | Locked choice from Phase 1 decision; supports device_name, PA_SAMPLE_S16LE, 16kHz; feature-complete |
| pulsectl | 24.12.0 | Enumerate output sinks for Settings → sound device picker | Already in pyproject.toml; sink_list() mirrors source_list() already used |
| wave (stdlib) | 3.10 | Write WAV headers + PCM data to temp file | No extra dependency; correct for s16le WAV |
| tempfile (stdlib) | 3.10 | Create temp WAV file in /tmp | NamedTemporaryFile(suffix='.wav', delete=False) |
| importlib.resources | 3.10 (stdlib) | Load bundled sound files at runtime | files() API stable since 3.9; use files(linux_speech_flow.sounds).joinpath('start.wav') |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| paplay (system binary) | pulseaudio-utils | Non-blocking WAV playback to specific sink | subprocess.Popen(['paplay', '--device=<sink>', path]) — returns immediately |
| notify-send (system binary) | libnotify-bin | Desktop notifications with replace support | subprocess.run(['notify-send', '-p', 'Recording...']) captures ID; Phase 3 uses -r ID |
| threading (stdlib) | 3.10 | Daemon threads for recording and Listener | threading.Thread(daemon=True) + threading.Event for stop signal |
| struct (stdlib) | 3.10 | Unpack PCM bytes for RMS silence calculation | struct.unpack(f'{n}h', chunk) → sample array |
| math (stdlib) | 3.10 | RMS calculation | math.sqrt(sum(s*s for s in samples) / len(samples)) |
| time (stdlib) | 3.10 | 300ms tap debounce (time.time() on key-down) | Compare time.time() - press_time >= 0.3 on key-up |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pynput Listener | python-xlib XGrabKey directly | XGrabKey is lower-level, harder to use correctly, requires X event loop management; pynput wraps this cleanly |
| paplay subprocess | pasimple for playback too | pasimple playback blocks until audio finishes — defeats non-blocking requirement |
| subprocess notify-send | GNotification (Gio.Notification) | GNotification via Gtk.Application is correct GTK4 way, but does NOT support replace-id for the Phase 2→3 notification chain; notify-send -r is required |
| importlib.resources | pkg_resources | pkg_resources is deprecated; importlib.resources.files() is the current standard |

**Installation:**
```bash
pip install pynput pasimple
# System dependencies (already present on Ubuntu/Pop!_OS):
# pulseaudio-utils (paplay), libnotify-bin (notify-send), libpulse0 (pasimple dep)
```

Add to pyproject.toml dependencies:
```toml
dependencies = [
    "requests>=2.31",
    "pulsectl>=24.0",
    "pynput>=1.8",
    "pasimple>=0.0.3",
]
```

## Architecture Patterns

### Recommended Project Structure
```
src/linux_speech_flow/
├── app.py              # Gtk.Application — starts HotkeyManager in do_startup
├── config.py           # load_config/save_config — add new defaults
├── audio.py            # list_microphones() — already exists; add list_sinks()
├── recorder.py         # NEW: AudioRecorder class — pasimple recording thread
├── hotkey.py           # NEW: HotkeyManager — pynput Listener, holds state machine
├── sounds.py           # NEW: play_sound() — paplay subprocess wrapper
├── notify.py           # NEW: send_notification() — notify-send wrapper, returns ID
├── settings.py         # EXTEND: add Audio section with 4 new fields
├── sounds/             # NEW directory: bundled WAV files
│   ├── start.wav
│   ├── stop.wav
│   └── error.wav
└── scripts/
    └── generate_sounds.py  # Dev-only: generates the 3 WAV files
```

### Pattern 1: Push-to-Talk State Machine in HotkeyManager

**What:** A state machine (IDLE → WAITING → RECORDING) managed in the pynput Listener thread, with GTK operations dispatched via GLib.idle_add.

**When to use:** Any time you need to bridge a background event thread to the GTK main loop.

**State transitions:**
- IDLE + F9_DOWN → record press_time, enter WAITING
- WAITING + F9_UP (< 300ms) → discard (tap), return to IDLE
- WAITING + F9_UP (>= 300ms) → start recording, enter RECORDING
- WAITING + 300ms elapsed (timer fires) → start recording, enter RECORDING
- RECORDING + F9_UP → stop recording normally
- RECORDING + ESC_DOWN → cancel recording (discard WAV)
- RECORDING + timeout → auto-stop normally
- RECORDING + silence detected → auto-stop normally

**Example:**
```python
# Source: pynput docs + verified pattern
import time
import threading
from pynput import keyboard
from gi.repository import GLib

class HotkeyManager:
    _STATE_IDLE = "idle"
    _STATE_WAITING = "waiting"
    _STATE_RECORDING = "recording"

    def __init__(self, config_getter, on_recording_complete, on_recording_error):
        self._state = self._STATE_IDLE
        self._press_time = None
        self._config_getter = config_getter
        self._on_complete = on_recording_complete
        self._on_error = on_recording_error
        self._recorder = None
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True

    def start(self):
        self._listener.start()

    def stop(self):
        self._listener.stop()

    def _on_press(self, key):
        if key == keyboard.Key.f9 and self._state == self._STATE_IDLE:
            self._press_time = time.monotonic()
            self._state = self._STATE_WAITING
        elif key == keyboard.Key.esc and self._state == self._STATE_RECORDING:
            GLib.idle_add(self._cancel_recording)

    def _on_release(self, key):
        if key == keyboard.Key.f9:
            if self._state == self._STATE_WAITING:
                elapsed = time.monotonic() - self._press_time
                if elapsed >= 0.3:
                    GLib.idle_add(self._start_recording)
                else:
                    self._state = self._STATE_IDLE
            elif self._state == self._STATE_RECORDING:
                GLib.idle_add(self._stop_recording, False)  # False = not cancelled
```

### Pattern 2: Recording Thread with Chunked Reads and Stop Event

**What:** AudioRecorder runs pasimple reads in a daemon thread, checking a `threading.Event` between each chunk. On stop, joins the thread and finalizes the WAV file.

**When to use:** Any blocking I/O that must not block the GTK main thread.

**Key insight:** pasimple `read()` is blocking per-chunk. Use small chunks (0.1s = 3200 bytes at 16kHz s16le) so the stop event is checked ~10 times/second. This also enables per-chunk RMS silence detection.

**Example:**
```python
# Source: pasimple README + threading stdlib docs
import pasimple
import wave
import struct
import math
import threading
import tempfile
import os

SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pasimple.PA_SAMPLE_S16LE
SAMPLE_WIDTH = 2  # s16le = 2 bytes
CHUNK_DURATION = 0.1  # seconds
CHUNK_BYTES = int(SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * CHUNK_DURATION)
SILENCE_RMS_THRESHOLD = 0.005  # fixed constant, ~-46 dBFS normalized

class AudioRecorder:
    def __init__(self, device_name, max_duration, silence_duration):
        self._device_name = device_name
        self._max_duration = max_duration
        self._silence_duration = silence_duration
        self._stop_event = threading.Event()
        self._cancel_flag = False
        self._wav_path = None
        self._thread = None
        self._on_complete = None
        self._on_error = None

    def start(self, on_complete, on_error):
        self._on_complete = on_complete
        self._on_error = on_error
        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        self._wav_path = tmp.name
        tmp.close()
        self._thread = threading.Thread(
            target=self._record_loop, daemon=True
        )
        self._thread.start()

    def stop(self, cancel=False):
        self._cancel_flag = cancel
        self._stop_event.set()

    def _record_loop(self):
        try:
            with pasimple.PaSimple(
                pasimple.PA_STREAM_RECORD,
                FORMAT, CHANNELS, SAMPLE_RATE,
                app_name='linux-speech-flow',
                stream_name='recording',
                device_name=self._device_name or None,
            ) as pa:
                with wave.open(self._wav_path, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(SAMPLE_WIDTH)
                    wf.setframerate(SAMPLE_RATE)
                    silence_chunks = 0
                    silence_limit = int(self._silence_duration / CHUNK_DURATION)
                    max_chunks = int(self._max_duration / CHUNK_DURATION)
                    chunks_recorded = 0
                    while not self._stop_event.is_set():
                        chunk = pa.read(CHUNK_BYTES)
                        wf.writeframes(chunk)
                        chunks_recorded += 1
                        # RMS silence detection
                        samples = struct.unpack(f'{len(chunk)//2}h', chunk)
                        rms = math.sqrt(
                            sum(s*s for s in samples) / len(samples)
                        ) / 32768.0
                        if rms < SILENCE_RMS_THRESHOLD:
                            silence_chunks += 1
                        else:
                            silence_chunks = 0
                        if silence_chunks >= silence_limit:
                            break  # auto-stop: silence
                        if chunks_recorded >= max_chunks:
                            break  # auto-stop: max duration
        except pasimple.PaSimpleError as e:
            self._handle_error(str(e))
            return
        if self._cancel_flag:
            os.unlink(self._wav_path)
            return
        from gi.repository import GLib
        GLib.idle_add(self._on_complete, self._wav_path)

    def _handle_error(self, msg):
        if os.path.exists(self._wav_path):
            os.unlink(self._wav_path)
        from gi.repository import GLib
        GLib.idle_add(self._on_error, msg)
```

### Pattern 3: Non-Blocking Sound Playback via paplay

**What:** `subprocess.Popen` launches paplay and returns immediately. The process plays the sound independently.

**When to use:** Any sound event (start, stop, error). Called from GLib.idle_add callback on main thread.

**paplay device flag:** `--device=<sink_name>` where sink_name is the PulseAudio sink name (e.g., `alsa_output.pci-0000_00_1f.3.analog-stereo`). If `sounds_output_device` config is empty string → omit `--device` flag (use PulseAudio default).

**Example:**
```python
# Source: paplay man page + subprocess docs
import subprocess
import importlib.resources

def play_sound(sound_name: str, output_device: str | None = None) -> None:
    """Play a bundled sound file non-blocking via paplay."""
    ref = importlib.resources.files('linux_speech_flow.sounds').joinpath(sound_name)
    with importlib.resources.as_file(ref) as path:
        cmd = ['paplay']
        if output_device:
            cmd.append(f'--device={output_device}')
        cmd.append(str(path))
        subprocess.Popen(cmd, stderr=subprocess.DEVNULL)
```

### Pattern 4: Desktop Notifications with Replace-ID Chain

**What:** `notify-send -p` prints the notification ID to stdout. Store it. Phase 3 passes this ID back via `notify-send -r <id>` to replace "Recording..." with "Transcribing...".

**Critical detail:** `notify-send -p` is only available in libnotify >= 0.7.9 (Ubuntu 22.04 ships 0.7.9). Test availability on target platform.

**Example:**
```python
# Source: notify-send(1) man page (Arch)
import subprocess

def send_notification(summary: str, body: str = '', replace_id: int | None = None) -> int | None:
    """Send desktop notification. Returns notification ID (for replacement chain)."""
    cmd = ['notify-send', '-p']  # -p = print ID to stdout
    if replace_id is not None:
        cmd += ['-r', str(replace_id)]
    cmd += [summary]
    if body:
        cmd.append(body)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        return int(result.stdout.strip()) if result.stdout.strip() else None
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return None
```

### Pattern 5: Enumerating Output Sinks for Settings

**What:** `pulsectl.Pulse.sink_list()` mirrors `source_list()` already used in audio.py. Add `list_sinks()` to audio.py.

**Example:**
```python
# Source: pulsectl library (already in pyproject.toml)
import pulsectl

def list_sinks() -> list[dict]:
    """Return available PulseAudio/PipeWire output sinks."""
    with pulsectl.Pulse('linux-speech-flow') as pulse:
        sinks = pulse.sink_list()
    return [
        {"name": s.name, "description": s.description}
        for s in sinks
    ]
```

### Pattern 6: Bundled WAV File Generation (dev-only script)

**What:** A one-time script generates the 3 WAV files using only Python stdlib (`wave`, `math`, `struct`). Output is committed to the repo. Not run at install time.

**Chime design:**
- `start.wav`: ascending two-tone (440 Hz → 880 Hz), 0.3s total, 10ms fade in/out
- `stop.wav`: descending two-tone (880 Hz → 440 Hz), 0.3s total, 10ms fade in/out
- `error.wav`: triple short buzz (200 Hz repeated 3×), 0.5s total, distinct from chimes

**Example:**
```python
# Source: Python wave stdlib docs + sine wave generation pattern
import wave, math, struct

def generate_tone(freq_hz, duration_s, sample_rate=22050, amplitude=0.3):
    n_samples = int(sample_rate * duration_s)
    fade = int(sample_rate * 0.01)  # 10ms fade
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        val = amplitude * math.sin(2 * math.pi * freq_hz * t)
        # fade in/out
        if i < fade:
            val *= i / fade
        elif i > n_samples - fade:
            val *= (n_samples - i) / fade
        samples.append(int(val * 32767))
    return struct.pack(f'{n_samples}h', *samples)

def write_wav(path, data, sample_rate=22050):
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data)
```

### Pattern 7: Startup Key-Held-Down Guard

**What:** Track a boolean `_started` in HotkeyManager. Set it True after the first GTK main loop tick (GLib.idle_add in do_startup). Only process F9 events when `_started` is True.

**Why:** If F9 is held when the app launches, the first key event arrives before `_started` is True — safely ignored. State machine in IDLE, so double key-up is also harmless.

**Example:**
```python
# In App.do_startup() or do_activate():
def _on_started(self):
    self._hotkey_manager.mark_started()
    return False  # remove from idle queue

GLib.idle_add(self._on_started)
```

### Anti-Patterns to Avoid

- **Calling GTK from pynput callback directly:** pynput callbacks fire from a non-GTK thread. Any `GLib/Gtk` call must be wrapped in `GLib.idle_add()`. Direct calls cause random crashes or silent no-ops.
- **Using pynput GlobalHotKeys for push-to-talk:** GlobalHotKeys only fires on press, not release. Use `Listener` with both `on_press` and `on_release`.
- **Restarting a stopped pynput Listener:** `Listener` is a `threading.Thread` — once stopped, it cannot be restarted. Create a new instance if needed.
- **Using suppress=True on X11:** Known to cause system-level crashes and session logouts on X11. Never use it.
- **Blocking the recording thread with file close before stop_event check:** Close the wave file inside the loop's natural exit, not in a finally that races with the stop flag.
- **Using pasimple's `record_wav()` convenience function:** It blocks for a fixed duration — not suitable for push-to-talk with dynamic stop.
- **Writing WAV frames without a header:** Always use `wave.open()` — raw PCM written directly won't be recognized by Groq's API.
- **Calling notify-send without -p and then trying to replace:** Without `-p` (print-id) on the first call, you have no ID to pass to `-r`. Always capture the ID at "Recording..." notification time.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| X11 global key grab | Custom XGrabKey via ctypes | pynput Listener | XGrabKey requires managing X event loop, modifier masks, key repeat filtering; pynput handles all of this |
| Non-blocking audio playback | Python thread playing WAV manually | subprocess.Popen(['paplay', ...]) | paplay handles format conversion, device routing, timing; one-liner |
| Audio device enumeration (sinks) | Parse `pactl list sinks` output | pulsectl sink_list() | Structured Python objects; already a dependency; robust |
| Package resource path resolution | __file__-relative paths | importlib.resources.files() | Works correctly in .deb/wheel installs where __file__ may be in a .zip |
| WAV file format | Raw PCM write | wave.open() | WAV headers (RIFF chunk, fmt chunk) are required; wave stdlib handles all byte ordering |

**Key insight:** X11 keyboard grabbing has significant complexity around modifier key masks, key repeat events, and grab ownership conflicts. pynput abstracts all of this correctly and has been battle-tested on X11.

## Common Pitfalls

### Pitfall 1: Key Repeat Events Causing Multiple Recording Starts
**What goes wrong:** When F9 is held, X11 sends repeated KeyPress events (key repeat). Without debouncing, on_press fires multiple times, potentially starting multiple recordings.
**Why it happens:** X11 key auto-repeat sends KeyRelease + KeyPress pairs at the repeat rate. pynput forwards all of these.
**How to avoid:** State machine prevents this naturally — only accept F9 press in IDLE state. If state is WAITING or RECORDING when a new F9 press arrives, ignore it.
**Warning signs:** Recording starts and immediately stops, or audio file is empty.

### Pitfall 2: pasimple Raises PaSimpleError at Stream Open, Not at Read
**What goes wrong:** If the microphone is unavailable (device disconnected, wrong name), `PaSimple()` raises `PaSimpleError` during `__init__` / `__enter__`, before any `read()` call.
**Why it happens:** PulseAudio establishes the connection during stream creation.
**How to avoid:** Wrap the entire `with pasimple.PaSimple(...) as pa:` block in try/except PaSimpleError. The error fires at context entry. The error message contains a PulseAudio error code integer (0–27); code 5 = "No such entity" (device not found); code 1 = "Access denied".
**Warning signs:** Exception fires immediately on recording start, never after first read.

### Pitfall 3: WAV File Left in /tmp on Crash
**What goes wrong:** If the app crashes mid-recording, the temp WAV file is never deleted.
**Why it happens:** NamedTemporaryFile(delete=False) requires manual cleanup; no cleanup runs on crash.
**How to avoid:** This is acceptable behavior for Phase 2 — /tmp is cleaned on reboot. Phase 2 must delete on cancel/error; Phase 3 deletes on transcription success. Document the known gap.
**Warning signs:** /tmp filling with .wav files after repeated crashes.

### Pitfall 4: notify-send -p Not Available on All Systems
**What goes wrong:** `notify-send -p` (print ID) was added in libnotify 0.7.9. Older Ubuntu releases or minimal installs may lack it.
**Why it happens:** Feature is relatively recent; some CI/test environments lack it.
**How to avoid:** Wrap notify-send calls to handle missing binary gracefully (FileNotFoundError) and return None for ID. The notification chain degrades to "no replace" but the app still functions.
**Warning signs:** `notify-send: unrecognized option '-p'` in stderr.

### Pitfall 5: pynput Listener Must Be Started Before GTK Main Loop Blocks
**What goes wrong:** If `listener.start()` is called after `app.run()`, it never runs because `app.run()` blocks the calling thread in the GLib main loop.
**Why it happens:** `app.run()` is blocking; code after it doesn't execute until the app exits.
**How to avoid:** Start HotkeyManager in `Gtk.Application.do_startup()` (called before do_activate, before main loop blocks) or use `GLib.idle_add` to defer it to first main loop tick.
**Warning signs:** F9 never responds; listener thread not visible in `ps`.

### Pitfall 6: Silence Detection False-Triggers at Recording Start
**What goes wrong:** The first 0–2 chunks after recording starts may be zeros (PulseAudio buffer fill latency), triggering silence auto-stop immediately.
**Why it happens:** PulseAudio buffers take a few ms to fill with real microphone data.
**How to avoid:** Add a mandatory minimum recording duration (e.g., 1 second / 10 chunks) before silence detection activates. Reset silence_chunks counter only after the minimum duration passes.
**Warning signs:** Recording stops within 1 second even when speaking.

### Pitfall 7: pasimple read() Blocking Prevents Responsive Stop
**What goes wrong:** If chunk size is too large (e.g., 1 second = 32000 bytes), the stop event isn't checked for up to 1 second after it's set, making cancel feel laggy.
**Why it happens:** `read()` blocks until exactly `num_bytes` bytes are available.
**How to avoid:** Use small chunks: 0.1s × 16000 Hz × 2 bytes = 3200 bytes. This checks the stop event 10 times per second. The existing VU meter in settings.py uses 800-byte chunks (50ms) as a confirmed working chunk size.
**Warning signs:** Escape cancel takes 1+ seconds to take effect.

## Code Examples

### Complete pyproject.toml with sounds package data
```toml
# Source: setuptools docs + pyproject.toml spec
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "linux-speech-flow"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.31",
    "pulsectl>=24.0",
    "pynput>=1.8",
    "pasimple>=0.0.3",
]

[project.scripts]
linux-speech-flow = "linux_speech_flow.app:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
linux_speech_flow = ["sounds/*.wav"]
```

### config.py DEFAULT_CONFIG additions
```python
# Source: existing config.py pattern — add new keys with defaults
DEFAULT_CONFIG = {
    "groq_api_key": "",
    "microphone": "",
    "vocabulary": [],
    "setup_complete": False,
    # Phase 2 additions:
    "sounds_enabled": True,
    "sounds_output_device": "",       # empty = system default
    "max_recording_duration": 300,    # seconds
    "silence_stop_duration": 10,      # seconds
}
```

### Settings Audio section — Gtk.Switch for toggle
```python
# Source: GTK4 Python docs pattern
audio_title = Gtk.Label(label="Audio")
audio_title.add_css_class("title-4")
audio_title.set_xalign(0)
content.append(audio_title)

sounds_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
sounds_label = Gtk.Label(label="Notification sounds")
sounds_label.set_hexpand(True)
sounds_label.set_xalign(0)
self._sounds_switch = Gtk.Switch()
self._sounds_switch.set_active(self._config.get("sounds_enabled", True))
sounds_row.append(sounds_label)
sounds_row.append(self._sounds_switch)
content.append(sounds_row)

self._sounds_sink_combo = Gtk.ComboBoxText()
# populated by _enumerate_sinks()
content.append(self._sounds_sink_combo)

self._max_duration_spin = Gtk.SpinButton.new_with_range(1, 600, 1)
self._max_duration_spin.set_value(self._config.get("max_recording_duration", 300))
content.append(self._max_duration_spin)

self._silence_spin = Gtk.SpinButton.new_with_range(1, 60, 1)
self._silence_spin.set_value(self._config.get("silence_stop_duration", 10))
content.append(self._silence_spin)
```

### HotkeyManager integration in App.do_startup
```python
# Source: GTK4 Gtk.Application lifecycle docs
from linux_speech_flow.hotkey import HotkeyManager

class App(Gtk.Application):
    def do_startup(self):
        super().do_startup()
        self._hotkey_manager = HotkeyManager(
            config_getter=load_config,
            on_recording_complete=self._on_recording_complete,
            on_recording_error=self._on_recording_error,
        )
        self._hotkey_manager.start()
        GLib.idle_add(self._hotkey_manager.mark_started)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| python-xlib XGrabKey directly | pynput Listener | ~2015 | Eliminates X event loop management; works with GTK |
| sounddevice/pyaudio for PulseAudio | pasimple (PulseAudio simple API) | Phase 1 decision | PortAudio 19.6.0 can't enumerate PipeWire devices |
| pkg_resources for package data | importlib.resources.files() | Python 3.9+ | pkg_resources deprecated; files() is stdlib |
| GObject.threads_init() | Not needed (GTK 4) | GTK4 | GTK4 is thread-safe without explicit init |
| Gtk.Assistant for wizards | Gtk.Stack (Phase 1 decided) | GTK 4.10 | Gtk.Assistant deprecated, removed in GTK5 |

**Deprecated/outdated:**
- `pynput GlobalHotKeys`: Does not support on_release callbacks — cannot implement push-to-talk hold behavior. Issue #267 in pynput repo confirms this limitation.
- `pasimple.record_wav()`: Blocking fixed-duration convenience function — useless for push-to-talk.
- `GObject.threads_init()`: Required in GTK3, not needed in GTK4.

## Open Questions

1. **pulsectl reliability with PipeWire for sink enumeration**
   - What we know: pulsectl uses libpulse; PipeWire implements pipewire-pulse compatibility layer; sink_list() and source_list() already work in Phase 1 code for source enumeration.
   - What's unclear: Multiple sources note "pulsectl no longer works reliably with PipeWire" in some configurations, though the pipewire-pulse layer usually fixes this.
   - Recommendation: sink_list() should work identically to source_list() since pulsectl already works for sources in Phase 1. If sink_list() fails, fall back to parsing `pactl list sinks` output.

2. **notify-send -p availability on target Ubuntu versions**
   - What we know: Ubuntu 22.04 ships libnotify 0.7.9 which includes -p. Pop!_OS 22.04 (target) inherits same packages.
   - What's unclear: Whether the CI/test environment has libnotify-bin installed.
   - Recommendation: Wrap in try/except FileNotFoundError and test explicitly. Return None gracefully when unavailable.

3. **HotkeyManager and single-instance: D-Bus activation vs. second-process detection**
   - What we know: Phase 1 uses Gtk.Application with D-Bus for single-instance. HotkeyManager must only run in the primary instance.
   - What's unclear: Whether `do_startup` vs `do_activate` is the right place to start the listener; `do_startup` runs only in the primary instance (not the second launch), which is correct.
   - Recommendation: Start HotkeyManager in `do_startup()`, confirmed correct for primary-only execution.

4. **pasimple error code for "device disconnected mid-recording"**
   - What we know: `PaSimpleError` is raised; error message includes a PulseAudio error code integer.
   - What's unclear: The exact error code for mid-recording device disconnect (likely code 5 "No such entity" or code 8 "I/O error").
   - Recommendation: Catch all `PaSimpleError` in the recording loop (not just at stream open) and treat any exception as "mic error". Don't attempt to distinguish specific codes.

## Sources

### Primary (HIGH confidence)
- pasimple GitHub README (henrikschnor/pasimple) — PaSimple constructor signature, device_name parameter, PA_SAMPLE_S16LE format, read() blocking behavior, PaSimpleError
- pasimple/pa_simple.py source — PaSimpleError raise conditions, stream creation failure handling, error code format
- pynput PyPI / pynput readthedocs — Listener API, on_press/on_release callbacks, daemon thread behavior, GLib.idle_add integration requirement
- Python 3.10 stdlib docs — wave, tempfile, importlib.resources.files(), struct, threading.Event
- notify-send(1) Arch man page — -p (print-id) and -r (replace-id) flags confirmed present
- paplay(1) Debian man page — --device flag for sink selection

### Secondary (MEDIUM confidence)
- PyGObject threading docs (pygobject.readthedocs.io) — GLib.idle_add pattern confirmed for background-thread-to-GTK-main-thread dispatch
- pynput issue #267 — confirms GlobalHotKeys does NOT support on_release; Listener required
- pynput issue #269 — confirms suppress=True crashes X11 sessions; never use it
- setuptools package-data docs — [tool.setuptools.package-data] glob pattern confirmed

### Tertiary (LOW confidence)
- "pulsectl no longer works reliably with PipeWire" — multiple WebSearch sources, but contradicted by Phase 1 working source_list(); treat as LOW risk for sink_list()
- pasimple PulseAudio error codes for specific failure modes (5 = no entity, 8 = I/O error) — from PulseAudio C API docs, not verified against pasimple's Python exception messages

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pasimple v0.0.3 confirmed, pynput 1.8.1 confirmed, all other tools are stdlib or system binaries
- Architecture: HIGH — patterns verified against official docs; threading model is standard GTK+background-thread pattern
- Pitfalls: HIGH — key repeat, PaSimpleError-at-open, silence false-trigger are verified from library source inspection; suppress=True crash is documented in pynput issue tracker

**Research date:** 2026-02-19
**Valid until:** 2026-03-21 (stable libraries; 30-day window)
