# Phase 3: Transcription & Text Injection - Research

**Researched:** 2026-02-19
**Domain:** Groq API (Whisper + LLM), clipboard injection (xclip/xdotool), GTK4 window detection, threading pipeline
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Post-processing style:**
- Smart cleanup: strip filler words (um, uh, like), fix repetitions, improve sentence flow — preserve meaning, do not paraphrase
- Preserve the user's casing intent; do not auto-capitalize unless clearly a sentence start
- Add terminal punctuation only if output is clearly a complete sentence; leave fragments unpunctuated
- Voice commands treated as formatting: "new line" → `\n`, "new paragraph" → `\n\n` in output
- Design for both short (one-sentence) and long (multi-paragraph) dictation in the same prompt
- LLM prompt is user-editable in settings (advanced section, with warnings about breaking behaviour)

**Window context usage:**
- Detect app category (terminal emulator, code editor, other) from active window class/title
- App category list is configurable in settings — user can add/override entries; ship with sensible defaults
- Terminal emulators: use Ctrl+Shift+V for paste
- Code editors: detected for LLM context; paste method and prompt adaptation: Claude's Discretion
- How window context feeds into the LLM prompt: Claude's Discretion
- Fallback when xdotool cannot detect active window (Wayland, locked screen): Claude's Discretion

**Error & edge case handling:**
- Whisper API failure: play error sound + desktop notification with specific message (separate text for: invalid API key / network error / rate limit exceeded)
- Silence or transcript too short to be meaningful: notify user (no paste, no sound)
- LLM post-processing failure: paste raw Whisper transcript as fallback + subtle notification "LLM failed — raw transcript pasted"
- Retry strategy: Fibonacci-scaled, starting at 5 s, up to 5 attempts (5 s, 8 s, 13 s, 21 s, 34 s) before giving up
- After all retries exhausted: save WAV to `~/.local/share/linux-speech-flow/failed/` (filename includes timestamp)
- Error notification informs user WAV was saved and F10 can reprocess

**F10 reprocess hotkey:**
- 1 failed WAV: retry pipeline immediately, paste as normal
- Multiple failed WAVs: open a small GTK dialog listing recordings by timestamp; user selects one or all
- "Reprocess All" batch mode: prompt user before starting — "Write all to file" or "Paste each into current window"
- Failed WAV storage: `~/.local/share/linux-speech-flow/failed/`; cleaned up on successful reprocess

**Feedback during wait:**
- Audio sequence per successful run: stop chime (Phase 2) → processing sound (one-shot, plays on F9 release) → success chime (plays when text is pasted)
- Both processing.wav and success.wav are new bundled files added to `src/linux_speech_flow/sounds/`
- All three sounds individually toggleable in settings
- Pipeline timeout: 60 seconds (default), configurable in settings
- F9 pressed while pipeline is running: queue the new recording; notify user "Recording queued (N pending)" when queued
- Queue processes in FIFO order

**Settings — new Transcription section:**
- Add a dedicated Transcription tab/section to SettingsWindow alongside the existing Audio section
- Fields: Groq LLM model selector, pipeline timeout (default: 60 s), processing/success sound toggles, app category list editor, advanced LLM system prompt editor with Reset to Default button

### Claude's Discretion

- How window context is embedded in the LLM post-processing prompt
- Custom vocabulary injection strategy in the prompt
- Code editor paste method (Ctrl+V assumed sufficient unless research shows otherwise)
- Fallback logic when active window cannot be detected
- Exact WAV file naming convention in the failed/ directory
- Retry applies to both Whisper and LLM calls individually or pipeline-wide (design the retry scope)
- Groq Whisper model version (default recommendation based on research)

### Deferred Ideas (OUT OF SCOPE)

- Tray icon state change during transcription — Phase 4
- Tray indicator for pending failed recordings — Phase 4
- KPI tracking per transcription run — Phase 5
- Multi-model A/B comparison — Phase 5 or standalone phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRANS-01 | Recorded audio is sent to Groq Whisper API (whisper-large-v3) for transcription | Groq SDK `client.audio.transcriptions.create()`, WAV format supported, whisper-large-v3 and whisper-large-v3-turbo both available |
| TRANS-02 | Raw transcript is sent to Groq LLM (meta-llama/llama-4-scout-17b-16e-instruct) for post-processing | Groq SDK `client.chat.completions.create()`, model confirmed available at ~750 tok/s, 128K context |
| TRANS-03 | Post-processing prompt includes active window title and application name as context | `xdotool getactivewindow` + `xprop -id WM_CLASS` for X11; session-type detection via `XDG_SESSION_TYPE` |
| TRANS-04 | Post-processed text is pasted into the focused application via clipboard (xclip + xdotool ctrl+v) | `xclip -selection clipboard` then `xdotool key ctrl+v` (or `ctrl+shift+v` for terminals); Wayland fallback via `wl-copy` |
| TRANS-05 | If post-processing fails, raw Whisper transcript is pasted as fallback | Groq SDK raises typed exceptions; catch `groq.APIError` subclasses, fallback to raw transcript |
| TRANS-06 | User can define a custom vocabulary list that is included in the post-processing prompt | Vocabulary already stored in `config["vocabulary"]` list; inject into system prompt as a hint section |
</phase_requirements>

---

## Summary

Phase 3 wires together three network calls (Whisper transcription, LLM post-processing) with two subprocess interactions (window detection, clipboard/paste injection). The `groq` Python SDK (v1.0.0) covers both API calls with typed exceptions and optional auto-retry. Window detection works cleanly on X11 via `xdotool getactivewindow` + `xprop WM_CLASS`; Wayland sessions need a graceful fallback (skip window context, use `wl-copy`/`ydotool` instead of `xdotool`). Threading must keep Groq calls off the GTK main thread, then dispatch results back via `GLib.idle_add` — the same pattern established in Phase 2's AudioRecorder.

The pipeline lifecycle is: WAV in → Whisper → LLM → clipboard write → xdotool paste → success sound → cleanup. Each step can fail independently; the retry strategy (Fibonacci 5-attempts) applies per API call (Whisper and LLM independently). A `queue.Queue` in the `TranscriptionPipeline` class serialises concurrent F9 presses into FIFO order without blocking recording.

**Primary recommendation:** Build `TranscriptionPipeline` as a class with a daemon worker thread consuming a `queue.Queue`, using the `groq` SDK's synchronous client on the worker thread, and dispatching all GTK side-effects via `GLib.idle_add`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `groq` | 1.0.0 | Whisper transcription + LLM post-processing | Official Groq SDK; typed exceptions, auto-retry, sync + async clients |
| `xclip` | system | Write text to X11 clipboard (-selection clipboard) | Required by TRANS-04; already listed in DIST-05 system deps |
| `xdotool` | system | Send Ctrl+V / Ctrl+Shift+V keystrokes to focused window | Required by TRANS-04; already listed in DIST-05 |
| `xprop` | system (x11-utils) | Read WM_CLASS of active window for app categorisation | Reliable; available on all X11 desktops |
| `queue.Queue` | stdlib | Thread-safe FIFO for recording pipeline serialisation | No external dep; established pattern for GTK worker threads |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `wl-copy` (wl-clipboard) | system | Clipboard write on Wayland | When `XDG_SESSION_TYPE=wayland` |
| `ydotool` | system | Keystroke injection on Wayland | Wayland fallback for paste (requires `ydotoold` daemon) |
| `notify-send` | system | Desktop notifications for errors | Already used in Phase 2 via `notify.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `groq` SDK | `requests` (already in deps) | SDK adds typed exceptions and auto-retry; `requests` requires manual multipart encoding for audio upload |
| `xclip` + `xdotool` | `pyperclip` | `pyperclip` is a thin wrapper around xclip/xsel anyway; direct subprocess gives finer control over `-selection clipboard` |
| Manual Fibonacci sleep | `backoff` library | `backoff` library adds a dep; Fibonacci sequence is 6 lines of Python; custom is simpler and avoids extra install |

**Installation (new additions to pyproject.toml):**
```bash
pip install groq>=1.0.0
```
System tools (already documented in DIST-05, no Python dep):
```
xclip, xdotool, x11-utils (for xprop), wl-clipboard (optional Wayland fallback)
```

---

## Architecture Patterns

### Recommended Module Structure
```
src/linux_speech_flow/
├── transcription.py        # TranscriptionPipeline — queue, worker thread, Whisper + LLM calls
├── groq_client.py          # Extend: add transcribe_audio() and postprocess_text() functions
├── window_context.py       # get_active_window_info() — xdotool/xprop, session detection, category lookup
├── injector.py             # paste_text() — xclip write + xdotool keystroke, Wayland fallback
├── reprocess_dialog.py     # GTK4 window for F10 multi-file reprocess selection
├── sounds/
│   ├── processing.wav      # New: one-shot sound on pipeline start
│   └── success.wav         # New: chime on paste complete
└── config.py               # Extend DEFAULT_CONFIG with Phase 3 keys
```

### Pattern 1: Worker Thread + GLib.idle_add Dispatch

The AudioRecorder established this: blocking I/O on a daemon thread, results sent to GTK thread via `GLib.idle_add`. TranscriptionPipeline follows the same contract.

```python
# Source: existing recorder.py pattern + queue stdlib docs
import queue
import threading
from gi.repository import GLib

class TranscriptionPipeline:
    def __init__(self, config_loader, on_paste_complete, on_error):
        self._queue = queue.Queue()
        self._on_paste_complete = on_paste_complete
        self._on_error = on_error
        self._config_loader = config_loader
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def submit(self, wav_path: str) -> int:
        """Submit a WAV for processing. Returns queue depth after insert."""
        self._queue.put(wav_path)
        return self._queue.qsize()

    def _run(self):
        while True:
            wav_path = self._queue.get()
            try:
                self._process(wav_path)
            except Exception as exc:
                GLib.idle_add(self._on_error, str(exc))
            finally:
                self._queue.task_done()

    def _process(self, wav_path: str):
        # Whisper -> LLM -> inject (all blocking, on worker thread)
        ...
        GLib.idle_add(self._on_paste_complete)
```

### Pattern 2: Groq SDK — Whisper Transcription

```python
# Source: https://console.groq.com/docs/speech-to-text
from groq import Groq

def transcribe_audio(client: Groq, wav_path: str, language: str = "en") -> str:
    with open(wav_path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=f,
            model="whisper-large-v3-turbo",
            response_format="text",
            language=language,
            temperature=0.0,
        )
    return result.strip()
```

**Model recommendation (Claude's Discretion):** Use `whisper-large-v3-turbo` as default. It runs at 216x real-time on Groq hardware ($0.04/hr vs $0.111/hr for large-v3). For a voice dictation app where sub-second API response matters, the speed advantage outweighs the marginal WER difference (12% vs 10.3%). The user-editable model setting (CONF-XX) lets advanced users switch to `whisper-large-v3` if they find accuracy insufficient.

### Pattern 3: Groq SDK — LLM Post-Processing

```python
# Source: https://console.groq.com/docs/model/meta-llama/llama-4-scout-17b-16e-instruct
from groq import Groq

def postprocess_transcript(
    client: Groq,
    raw_transcript: str,
    system_prompt: str,
    window_info: dict,
    vocabulary: list[str],
) -> str:
    user_content = _build_user_message(raw_transcript, window_info, vocabulary)
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()
```

### Pattern 4: Window Context Detection

```python
# Source: xdotool man page + xprop docs (verified via WebSearch)
import os
import subprocess

def get_active_window_info() -> dict:
    """Returns {"title": str, "wm_class": str, "category": str} or empty on failure."""
    session = os.environ.get("XDG_SESSION_TYPE", "x11").lower()
    if session == "wayland":
        return {"title": "", "wm_class": "", "category": "other", "wayland": True}

    try:
        win_id = subprocess.check_output(
            ["xdotool", "getactivewindow"], text=True, timeout=2
        ).strip()
        title = subprocess.check_output(
            ["xdotool", "getwindowname", win_id], text=True, timeout=2
        ).strip()
        xprop_out = subprocess.check_output(
            ["xprop", "-id", win_id, "WM_CLASS"], text=True, timeout=2
        )
        # WM_CLASS(STRING) = "instance", "ClassName"
        wm_class = xprop_out.split("=")[-1].strip().strip('"').split('", "')[-1].rstrip('"')
        return {"title": title, "wm_class": wm_class, "category": _classify(wm_class)}
    except Exception:
        return {"title": "", "wm_class": "", "category": "other"}
```

### Pattern 5: Clipboard Write + Paste Injection

```python
# Source: xclip man page + xdotool man page
import subprocess

def paste_text(text: str, app_category: str, session_type: str = "x11") -> None:
    if session_type == "wayland":
        _wayland_paste(text)
        return
    # Write to clipboard selection (Ctrl+V clipboard, not primary)
    proc = subprocess.Popen(
        ["xclip", "-selection", "clipboard"],
        stdin=subprocess.PIPE,
    )
    proc.communicate(text.encode("utf-8"))
    # Small delay to ensure clipboard is set before keystroke
    import time; time.sleep(0.05)
    # Send paste keystroke to focused window
    if app_category == "terminal":
        subprocess.run(["xdotool", "key", "ctrl+shift+v"], check=True)
    else:
        subprocess.run(["xdotool", "key", "ctrl+v"], check=True)

def _wayland_paste(text: str) -> None:
    proc = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
    proc.communicate(text.encode("utf-8"))
    import time; time.sleep(0.05)
    # ydotool requires ydotoold daemon; fall back to notify if unavailable
    try:
        subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=True)
    except FileNotFoundError:
        pass  # Wayland paste without ydotool: text in clipboard, user pastes manually
```

### Pattern 6: Fibonacci Retry

```python
# Source: algorithm + backoff library docs (fibonacci sequence)
import time

FIBONACCI_DELAYS = [5, 8, 13, 21, 34]  # seconds — 5 attempts

def call_with_retry(fn, *args, retryable_exceptions, **kwargs):
    """Call fn(*args, **kwargs), retrying on retryable_exceptions with Fibonacci backoff."""
    last_exc = None
    for delay in FIBONACCI_DELAYS:
        try:
            return fn(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exc = exc
            time.sleep(delay)
    raise last_exc
```

**Retry scope (Claude's Discretion):** Apply retry independently per API call. Whisper retries up to 5 times; if Whisper succeeds, LLM retries up to 5 times. This gives each layer its own budget and avoids the whole pipeline retrying when only LLM is unstable.

### Pattern 7: LLM System Prompt with Context Embedding

**Claude's Discretion — recommended design:**

Inject window context as a structured XML-style block inside the system prompt to clearly separate instructions from context. Vocabulary is a separate list block.

```
You are a transcription cleanup assistant. The user dictated the text below.
Your task:
- Remove filler words (um, uh, like, you know)
- Fix obvious repetitions
- Improve sentence flow without changing meaning or paraphrasing
- Preserve the user's original casing intent
- Add terminal punctuation only if the output is clearly a complete sentence; leave fragments without punctuation
- Interpret spoken formatting commands literally: "new line" → newline character, "new paragraph" → two newlines

<context>
Application: {wm_class}
Window title: {title}
App category: {category}
</context>

<vocabulary>
The following words or phrases are correct and must not be altered:
{vocabulary_list}
</vocabulary>

Return ONLY the cleaned text. No explanations, no prefixes.
```

The `<context>` block is omitted entirely when window detection fails (Wayland or error).
The `<vocabulary>` block is omitted when the vocabulary list is empty.

**Code editor paste method (Claude's Discretion):** Use standard `Ctrl+V` for code editors. Research found no evidence that common editors (VS Code, vim, neovim, emacs) require anything other than Ctrl+V for clipboard paste. The terminal emulator `Ctrl+Shift+V` exception is the only documented special case.

### Pattern 8: Failed WAV Naming Convention

**Claude's Discretion — recommended design:**

```
~/.local/share/linux-speech-flow/failed/
    recording_20260219T143022_abc3.wav
```

Format: `recording_{ISO8601_compact}_{4char_random}.wav`

Python: `f"recording_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:4]}.wav"`

The timestamp makes listings chronological; the 4-char random suffix prevents collisions if two recordings finish within the same second.

### Pattern 9: Sound Generation for New Files

The existing `generate_sounds.py` script generates WAV files programmatically. Add `processing.wav` and `success.wav` using the same `generate_tone()` approach.

```python
# processing.wav: ascending two-note (optimistic, "starting work")
proc_data = generate_tone(523, 0.1) + generate_tone(659, 0.1)  # C5 → E5
write_wav(OUT_DIR / "processing.wav", proc_data)

# success.wav: three ascending tones (completion fanfare, distinct from start/stop)
succ_data = generate_tone(523, 0.1) + generate_tone(659, 0.1) + generate_tone(784, 0.15)  # C5→E5→G5
write_wav(OUT_DIR / "success.wav", succ_data)
```

### Anti-Patterns to Avoid

- **Calling xdotool from the GTK main thread:** Any subprocess call that can block (window detection, clipboard write) must run on the worker thread. GTK freezes if the main thread waits on a subprocess.
- **Re-reading config inside the worker thread without a lock:** `load_config()` reads JSON from disk; multiple concurrent calls are safe (file read only), but pass config into the pipeline at submission time rather than re-reading mid-flight.
- **Putting text on the primary X11 selection:** Must use `-selection clipboard` for Ctrl+V compatibility. Primary selection is middle-mouse-button only.
- **Sending Ctrl+V before xclip process exits:** Add a `proc.communicate()` or `proc.wait()` call, plus a brief sleep, to ensure clipboard content is committed before xdotool fires.
- **Using Gtk.Dialog directly:** `Gtk.Dialog` is deprecated since GTK 4.10. Use `Gtk.Window` with `set_modal(True)` and `set_transient_for(parent)` for the reprocess dialog.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Groq API auth/retry/backoff | Custom HTTP retry | `groq` SDK with `max_retries` parameter | SDK handles connection errors, 429, 5xx with exponential backoff automatically |
| Groq error classification | Parse HTTP status manually | `groq.AuthenticationError`, `groq.RateLimitError`, `groq.APIConnectionError` | SDK raises typed exceptions; direct import and isinstance check |
| Thread-safe FIFO queue | Custom list + locks | `queue.Queue` | Already implements locking, blocking `.get()`, and `.task_done()` |
| Clipboard operations | Direct X11 protocol | `xclip` subprocess | X11 clipboard is complex; xclip handles encoding and selection types correctly |

**Key insight:** The Groq SDK auto-retries 2 times by default on transient errors. Set `max_retries=0` on the client to take full control with the custom Fibonacci retry wrapper.

---

## Common Pitfalls

### Pitfall 1: xdotool keystroke targets wrong window

**What goes wrong:** `xdotool key ctrl+v` sends the keystroke to the window that has focus at the moment of execution, not the window that had focus when F9 was pressed. If the processing notification pop-up, the GTK placeholder window, or any other window grabs focus during the pipeline, the text pastes into the wrong place.

**Why it happens:** The pipeline takes 1-10+ seconds. Any GTK `present()` call or notification click can steal focus.

**How to avoid:** Capture the active window ID at the start of `_on_recording_complete` (before the pipeline starts), then pass `--window {saved_id}` to xdotool at paste time: `xdotool key --window {win_id} ctrl+v`. Also capture the window ID before sending the "processing" notification.

**Warning signs:** Text appears in the app's own notification area or settings window.

### Pitfall 2: Whisper rejects audio below minimum length

**What goes wrong:** The Groq Whisper API requires a minimum of 0.01 seconds, with a 10-second minimum billable unit. Very short recordings (button tap with no speech) return empty or near-empty transcripts.

**Why it happens:** Recorder auto-stops on silence. A fast tap produces a WAV with only silence frames.

**How to avoid:** After receiving the raw transcript from Whisper, check `len(transcript.strip()) < 3`. If so, play no success sound, show a notification "No speech detected", and discard the WAV without pasting.

**Warning signs:** Empty pastes or a literal space character appearing in the focused application.

### Pitfall 3: xclip hangs if no X display is available

**What goes wrong:** `subprocess.Popen(["xclip", ...])` hangs indefinitely if `DISPLAY` is not set (running headless, SSH without X forwarding, or Wayland-only sessions).

**Why it happens:** xclip requires a running X server to connect to. Without `DISPLAY`, the process blocks waiting for X.

**How to avoid:** Check `os.environ.get("DISPLAY")` before calling xclip. On Wayland (where DISPLAY may still be set via XWayland), prefer the `XDG_SESSION_TYPE` check. Always pass a `timeout` to `subprocess.run()`.

**Warning signs:** Pipeline hangs indefinitely; timeout mechanism never fires because the subprocess itself is blocking.

### Pitfall 4: Groq SDK default retries conflict with custom Fibonacci retry

**What goes wrong:** The `groq` SDK retries 2 times by default on 429 and 5xx. If the pipeline also applies a Fibonacci retry wrapper, total retry attempts become 2 × 5 = 10, with delays multiplied by SDK's own backoff + custom backoff. The total wait time becomes unpredictable and can far exceed the 60-second pipeline timeout.

**How to avoid:** Instantiate the Groq client with `max_retries=0` to disable SDK auto-retry entirely. Let the Fibonacci wrapper be the sole retry mechanism.

```python
client = Groq(api_key=api_key, max_retries=0)
```

**Warning signs:** Pipeline timeout fires before all expected Fibonacci retry attempts complete.

### Pitfall 5: LLM post-processing returns markdown or prefixed text

**What goes wrong:** The LLM adds "Here is the cleaned text:" or wraps the output in markdown code fences when the system prompt is not explicit enough.

**Why it happens:** LLMs default to conversational, formatted output.

**How to avoid:** End the system prompt with "Return ONLY the cleaned text. No explanations, no prefixes, no markdown." Set `temperature=0.0` to reduce hallucination of extra content.

**Warning signs:** The pasted text starts with "Here is..." or contains triple-backtick fences.

### Pitfall 6: `GLib.idle_add` called from a thread that's already on the GTK main thread

**What goes wrong:** Double-dispatching causes subtle UI inconsistencies or the callback running twice.

**Why it happens:** The pipeline worker thread always calls `GLib.idle_add(callback)`. If the test harness or a synchronous path calls the same function from the main thread, the dispatch wrapper fires redundantly.

**How to avoid:** `GLib.idle_add` is always safe to call from any thread; it enqueues to the main loop. Keep all GTK side-effects (sound play, notification send, paste) gated through `GLib.idle_add` even if the caller is already on the main thread — it still works, just adds one loop iteration of latency.

### Pitfall 7: Race between WAV cleanup and pipeline retry

**What goes wrong:** `_on_recording_complete` currently does `os.unlink(wav_path)` immediately. Phase 3 must not delete the WAV until the pipeline succeeds or exhausts retries.

**Why it happens:** Phase 2's stub handler deleted the WAV as a placeholder. Phase 3 replaces this with `pipeline.submit(wav_path)` and the pipeline worker owns WAV lifecycle.

**How to avoid:** The pipeline worker deletes the WAV on success, or moves it to `~/.local/share/linux-speech-flow/failed/` on retry exhaustion. `_on_recording_complete` in `app.py` must not delete the WAV — just call `self._pipeline.submit(wav_path)`.

---

## Code Examples

### Groq Error Classification

```python
# Source: https://github.com/groq/groq-python (verified)
import groq

def _classify_groq_error(exc: groq.APIError) -> str:
    if isinstance(exc, groq.AuthenticationError):
        return "Invalid API key — check Settings"
    if isinstance(exc, groq.RateLimitError):
        return "Rate limit exceeded — try again shortly"
    if isinstance(exc, groq.APIConnectionError):
        return "Network error — check your internet connection"
    return f"Groq API error ({exc.status_code if hasattr(exc, 'status_code') else 'unknown'})"
```

### Window ID Capture Before Notification

```python
# Source: xdotool man page pattern
import subprocess

def capture_active_window_id() -> str | None:
    try:
        return subprocess.check_output(
            ["xdotool", "getactivewindow"], text=True, timeout=2
        ).strip()
    except Exception:
        return None
```

### Config Keys for Phase 3 (DEFAULT_CONFIG additions)

```python
# Source: config.py DEFAULT_CONFIG pattern
{
    # Phase 3 additions
    "whisper_model": "whisper-large-v3-turbo",
    "llm_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "pipeline_timeout": 60,
    "processing_sound_enabled": True,
    "success_sound_enabled": True,
    "app_categories": {
        "terminals": ["gnome-terminal", "kitty", "alacritty", "xterm", "konsole", "tilix", "xfce4-terminal"],
        "editors": ["code", "vim", "nvim", "neovim", "emacs", "sublime_text", "gedit", "kate"],
    },
    "llm_system_prompt": "...",  # default prompt string
}
```

### GTK4 Reprocess Dialog (Gt.Window, not deprecated Gtk.Dialog)

```python
# Source: https://docs.gtk.org/gtk4/class.Window.html
# Gtk.Dialog deprecated in GTK 4.10; use Gtk.Window with set_modal + set_transient_for
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

class ReprocessDialog(Gtk.Window):
    def __init__(self, failed_wavs: list[str], on_selected, application=None, parent=None):
        super().__init__(title="Reprocess Recordings", application=application)
        self.set_modal(True)
        if parent:
            self.set_transient_for(parent)
        self.set_default_size(420, 300)
        # ... build checkbox list from failed_wavs ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Gtk.Dialog` | `Gtk.Window` with `set_modal(True)` + `set_transient_for()` | GTK 4.10 | Gtk.Dialog deprecated; use plain Window for all dialog-like UIs |
| `requests` multipart for Groq audio | `groq` SDK `client.audio.transcriptions.create()` | groq SDK 1.0.0 (Dec 2025) | SDK handles multipart encoding, auth headers, retries |
| `whisper-large-v3` as default | `whisper-large-v3-turbo` recommended for real-time use | Turbo available since 2024 | 216x real-time speed at 36% of the cost; WER 12% vs 10.3% — acceptable trade |
| `xdotool type "text"` for text injection | `xclip -selection clipboard` + `xdotool key ctrl+v` | — | `xdotool type` breaks on special characters, Unicode; clipboard approach is robust |

**Deprecated/outdated:**
- `Gtk.Dialog`: Deprecated since GTK 4.10. The existing codebase uses GTK 4.0 (gi.require_version "Gtk", "4.0") — check actual GTK runtime version. If GTK >= 4.10 is present, use Gtk.Window. Both work; Gtk.Window is forward-compatible.
- `xdotool type` for text: Avoid for arbitrary Unicode. Only use `xdotool key` for keystrokes.

---

## Open Questions

1. **Wayland paste without ydotool**
   - What we know: `wl-copy` writes to Wayland clipboard. `ydotool` sends keystrokes but requires a running `ydotoold` daemon that most users won't have.
   - What's unclear: Is there a reliable keystroke injection method available on Wayland without daemon setup?
   - Recommendation: For Phase 3, on Wayland: write to clipboard via `wl-copy`, skip the keystroke. Show notification "Text copied to clipboard — press Ctrl+V to paste." This avoids a hard dependency on `ydotoold`. The v2 requirement WAY-01 covers proper Wayland injection.

2. **GTK runtime version vs GTK 4.10 deprecation**
   - What we know: Project uses `gi.require_version("Gtk", "4.0")`. GTK 4.10 deprecated `Gtk.Dialog`.
   - What's unclear: Ubuntu 22.04 ships GTK 4.6; Ubuntu 24.04 ships GTK 4.12. The deprecation warning only fires on GTK >= 4.10.
   - Recommendation: Use `Gtk.Window` with `set_modal`/`set_transient_for` from the start — it works on all GTK 4.x versions and avoids the deprecation entirely.

3. **Minimum transcript length threshold for "meaningful" speech**
   - What we know: Groq Whisper returns empty string `""` for silence; may return punctuation-only or single-char strings.
   - What's unclear: What length is "too short to be meaningful" in the user's context?
   - Recommendation: Use `len(transcript.strip()) < 3` as the threshold. This catches empty, single characters, and common Whisper artifacts like "." or "Hmm." Consider making this configurable in a later phase.

---

## Sources

### Primary (HIGH confidence)
- Groq official docs `https://console.groq.com/docs/speech-to-text` — Whisper API, models, parameters, file limits
- Groq official docs `https://console.groq.com/docs/model/meta-llama/llama-4-scout-17b-16e-instruct` — LLM model ID, context window, rate
- Groq official docs `https://console.groq.com/docs/errors` — Error types, HTTP codes
- PyPI `https://pypi.org/project/groq/` — SDK version 1.0.0, Python 3.9+ requirement
- GitHub `https://github.com/groq/groq-python` — Exception class names: AuthenticationError, RateLimitError, APIConnectionError
- GTK4 docs `https://docs.gtk.org/gtk4/class.Window.html` — Gtk.Window.set_modal, set_transient_for
- GTK4 docs `https://docs.gtk.org/gtk4/class.Dialog.html` — Confirms Gtk.Dialog deprecated since 4.10

### Secondary (MEDIUM confidence)
- xdotool Ubuntu man page `https://manpages.ubuntu.com/manpages/trusty/man1/xdotool.1.html` — getactivewindow, getwindowname, key commands
- Multiple sources confirming `XDG_SESSION_TYPE` env var as reliable Wayland/X11 detection method
- Groq blog `https://groq.com/blog/whisper-large-v3-turbo-now-available-on-groq-combining-speed-quality-for-speech-recognition` — 216x speed factor, turbo model positioning

### Tertiary (LOW confidence — verify before using)
- WebSearch results on ydotool Wayland keystroke injection — `ydotoold` daemon requirement confirmed by multiple community sources but no official doc URL verified
- GTK4 Python tutorial GitHub (`https://github.com/Taiko2k/GTK4PythonTutorial`) — dialog patterns, not official GNOME docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — groq SDK 1.0.0 confirmed on PyPI; xclip/xdotool from REQUIREMENTS.md DIST-05
- Architecture: HIGH — follows established recorder.py threading pattern; queue.Queue is stdlib
- Pitfalls: HIGH for items 1, 4, 7 (verified); MEDIUM for items 2, 3, 5, 6 (based on API docs + patterns)
- Window detection: HIGH for X11; MEDIUM for Wayland (ydotool daemon uncertainty)
- LLM prompt design: MEDIUM — recommended approach, requires validation with real dictation

**Research date:** 2026-02-19
**Valid until:** 2026-03-21 (30 days — Groq model availability changes; re-check if models page changes)
