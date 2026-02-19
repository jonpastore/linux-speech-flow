# Phase 2 Context: Audio Capture & Hotkey

## Source

Decisions captured via discuss-phase session on 2026-02-19.
Phase goal: User holds F9 → recording starts via pasimple → user releases F9 → WAV produced → audible feedback confirms start/stop.

---

## Area 1: F9 Hold Behavior

**Brief tap (< 300ms):** Ignore silently. No recording started, no feedback. Threshold: 300ms minimum hold before recording begins.

**Cancel:** Escape key cancels an in-progress recording. On cancel: stop recording immediately, discard the partial WAV, do not pass to transcription. Play the normal stop sound (same as a regular stop — confirms recording ended).

**Max duration:** 300 seconds default. User-configurable in Settings → Audio section. When max is hit: auto-stop recording and produce WAV for transcription (not an error condition — treat as normal stop).

**Silence auto-stop:** If RMS stays below threshold for N consecutive seconds → auto-stop recording and produce WAV. Default: 10 seconds of silence triggers stop. N is configurable in Settings → Audio section. Silence threshold (RMS level) is a fixed implementation constant — only the duration is user-configurable.

**Key held at startup:** Ignore. App only responds to fresh key-down events detected after startup.

---

## Area 2: Audio Feedback Sounds

**Source:** Bundled audio files shipped with the package. Style: soft chime / notification (not harsh beeps).

**Events covered:**
- Recording start → soft chime up / ascending tone
- Recording stop (normal) → soft chime down / descending tone
- Error (mic unavailable, mid-record failure) → error sound distinct from start/stop

**Generation:** Create WAV files programmatically using Python's `wave` module during development (sine wave with fade-in/out). Store in `src/linux_speech_flow/sounds/` and include as package data in `pyproject.toml`.

**Playback:** Use `paplay` (PulseAudio/PipeWire) for non-blocking sound playback. Target the user-configured output sink.

**Output device:** User-configurable in Settings → Audio section (ComboBoxText of PulseAudio/PipeWire sinks, i.e., output devices — not input sources). Separate from the microphone (input) device. Default: system default sink.

**On/off toggle:** Global sounds on/off toggle in Settings → Audio section. When off, no sounds play for any event (start, stop, error).

---

## Area 3: Error Handling UX

**Mic unavailable when F9 pressed:** Play error sound (if sounds enabled) + send desktop notification (libnotify) with message: "Microphone unavailable — check Settings". Do not enter recording state.

**Mic disappears mid-recording (e.g., USB unplugged):** Stop recording immediately. Play error sound + send desktop notification. Discard partial WAV — do not pass to transcription.

**Visual indicator during recording:** Send a desktop notification (libnotify) when recording starts: "Recording...". Phase 2 leaves this notification open. Phase 3 replaces it with "Transcribing..." using `notify-send --replace-id` when transcription begins. This notification chain (Recording → Transcribing → Done) spans Phase 2 and 3. This is the Phase 2 recording state indicator; Phase 4 will add tray icon state changes.

---

## Area 4: WAV File Lifecycle

**Location:** Python `tempfile.NamedTemporaryFile` in system `/tmp`. File is created before recording starts, written to during recording.

**Format:** 16kHz, mono, s16le (signed 16-bit little-endian). This is the optimal format for Groq Whisper — no conversion needed before API upload in Phase 3.

**Cleanup:** Phase 2 produces the WAV and passes the path. Phase 3 deletes the file immediately after transcription succeeds. On recording error or cancel: delete immediately in Phase 2.

---

## Area 5: Settings Window Changes (Phase 2 additions)

Add an **"Audio"** section to the existing `SettingsWindow` (settings.py) below the Microphone section. New fields:

| Field | UI | Default | Config key |
|---|---|---|---|
| Sounds on/off | Toggle switch | On | `sounds_enabled` |
| Sound output device | ComboBoxText (PulseAudio sinks) | System default | `sounds_output_device` |
| Max recording duration (sec) | SpinButton (1–600) | 300 | `max_recording_duration` |
| Silence auto-stop duration (sec) | SpinButton (1–60) | 10 | `silence_stop_duration` |

Config keys added to `~/.config/freeflow/config.json` schema. Default values must be applied when keys are absent (backward-compatible with Phase 1 configs).

---

## Deferred Ideas (out of scope for Phase 2)

- Hotkey configurability (remapping F9 to a different key) — Phase 6 or later
- Per-recording volume normalization — post-Phase 3 concern
- Visual waveform display during recording — deferred to Phase 4 or later
- Silence threshold (RMS level) as a user-configurable field — fixed constant in implementation
