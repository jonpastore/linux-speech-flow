---
phase: 02-audio-capture-and-hotkey
verified: 2026-02-19T15:30:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
human_verification:
  - test: "Confirm toggle mode (F9=start, ESC=stop) satisfies project intent for CORE-01/CORE-02"
    expected: "Phase goal stated 'hold F9 to record' but implementation uses toggle mode — press F9 to start, press ESC to stop. Human approved this during Plan 05 human verification. Confirm this is acceptable as the permanent interaction model before marking phase complete."
    why_human: "CORE-01 says 'User can hold F9 to begin audio recording' — toggle mode satisfies the start-recording half but not the release-to-stop half. REQUIREMENTS.md marks CORE-01 and CORE-02 as Complete, but no explicit requirement update was made to reflect toggle mode. This is a UX model decision that cannot be verified programmatically."
---

# Phase 2: Audio Capture & Hotkey Verification Report

**Phase Goal:** User can hold F9 to record audio from their microphone and hear audible feedback confirming recording start/stop
**Verified:** 2026-02-19T15:30:00Z
**Status:** human_needed (11/12 automated truths verified; 1 UX model question for human)
**Re-verification:** No — initial verification

## Implementation Deviation: Hold-to-Record vs Toggle Mode

The implementation differs meaningfully from the stated phase goal. The plans (01-04) describe hold-to-record (F9 held = recording, F9 released = stop). During Plan 05 human testing, hold-to-record was found impractical for longer dictation. The implementation was changed to **toggle mode**: press F9 to start recording, press ESC to stop. This was human-approved and committed in `f5bcee5`.

All code artifacts and wiring are correct and complete for the toggle model. The question for human verification is whether this UX model change is the intended permanent behavior.

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | pyproject.toml declares pynput>=1.8 and pasimple>=0.0.3 as dependencies | VERIFIED | pyproject.toml lines 12-13 contain both deps; `.venv/bin/python -c "import pynput; import pasimple"` succeeds |
| 2  | pyproject.toml includes sounds/*.wav as package data | VERIFIED | `[tool.setuptools.package-data]` section with `linux_speech_flow = ["sounds/*.wav"]` present |
| 3  | config.py DEFAULT_CONFIG contains all four Phase 2 keys with correct defaults | VERIFIED | `sounds_enabled=True`, `sounds_output_device=""`, `max_recording_duration=300`, `silence_stop_duration=10` all present |
| 4  | load_config() returns Phase 2 keys even when loading a Phase 1 config that lacks them | VERIFIED | load_config() uses `config = dict(DEFAULT_CONFIG); config.update(data)` — defaults backfill missing keys |
| 5  | audio.list_sinks() returns PulseAudio/PipeWire output sinks as list of dicts | VERIFIED | list_sinks() exists, returns `list`, swallows PulseError (returns `[]`), confirmed callable |
| 6  | Three WAV files exist in sounds/ (start.wav, stop.wav, error.wav) | VERIFIED | All three exist; valid mono 22050Hz 16-bit WAV headers; start/stop: 6614 frames, error: 8819 frames |
| 7  | play_sound() non-blocking via paplay; enabled=False is a no-op | VERIFIED | `subprocess.Popen` used (non-blocking); `if not enabled: return` at top; confirmed no subprocess spawned when disabled |
| 8  | play_sound() resolves WAV paths via importlib.resources (not `__file__`) | VERIFIED | `importlib.resources.files("linux_speech_flow.sounds").joinpath(sound_name)` confirmed in source |
| 9  | send_notification() returns int ID or None gracefully | VERIFIED | Returns `int(stripped)` on success, catches `TimeoutExpired, ValueError, FileNotFoundError, OSError` and returns None |
| 10 | AudioRecorder captures audio in daemon thread; callbacks dispatch via GLib.idle_add | VERIFIED | `threading.Thread(target=self._record_loop, daemon=True)`; `GLib.idle_add(self._on_complete, ...)` and `GLib.idle_add(self._on_error, ...)` in recorder.py |
| 11 | HotkeyManager wired into App.do_startup(); mark_started guard active; shutdown stops listener | VERIFIED | `do_startup()` creates and starts HotkeyManager; `GLib.idle_add(self._hotkey_manager.mark_started)`; `do_shutdown()` calls `stop()` |
| 12 | F9 press starts recording with start chime + notification; ESC stops with stop chime; error path plays error.wav | VERIFIED (toggle model) | `_on_press`: F9 in IDLE -> `_start_recording` (plays start.wav, sends notification, starts AudioRecorder); ESC in RECORDING -> `_stop_recording(cancel=False)` -> recorder completes -> `_on_recorder_complete` plays stop.wav; error path: `_on_recorder_error` plays error.wav |

**Score:** 12/12 truths verified (automated) — 1 UX model question requires human sign-off

---

### Required Artifacts

| Artifact | Status | Evidence |
|----------|--------|----------|
| `pyproject.toml` | VERIFIED | Contains `pynput>=1.8`, `pasimple>=0.0.3`, `sounds/*.wav` package-data |
| `src/linux_speech_flow/config.py` | VERIFIED | DEFAULT_CONFIG has all 4 Phase 2 keys; load_config() merges defaults |
| `src/linux_speech_flow/audio.py` | VERIFIED | list_sinks() implemented; list_microphones() preserved |
| `src/linux_speech_flow/sounds/__init__.py` | VERIFIED | play_sound() implementation (relocated from sounds.py due to Python naming collision with sounds/ package) |
| `src/linux_speech_flow/sounds/start.wav` | VERIFIED | 6614 frames, mono, 22050Hz, 16-bit |
| `src/linux_speech_flow/sounds/stop.wav` | VERIFIED | 6614 frames, mono, 22050Hz, 16-bit |
| `src/linux_speech_flow/sounds/error.wav` | VERIFIED | 8819 frames, mono, 22050Hz, 16-bit |
| `src/linux_speech_flow/scripts/generate_sounds.py` | VERIFIED | Exists; dev tool for WAV regeneration |
| `src/linux_speech_flow/notify.py` | VERIFIED | send_notification() with -p flag, returns int or None |
| `src/linux_speech_flow/recorder.py` | VERIFIED | AudioRecorder class, 140 lines, full implementation |
| `src/linux_speech_flow/hotkey.py` | VERIFIED | HotkeyManager, toggle mode, all GTK calls via idle_add, 154 lines |
| `src/linux_speech_flow/settings.py` | VERIFIED | Audio section present with all 4 Phase 2 fields; _on_save writes all 4 keys |
| `src/linux_speech_flow/app.py` | VERIFIED | do_startup() wires HotkeyManager; do_shutdown() stops it |

**Note on sounds.py vs sounds/__init__.py:** Plan 02 specified `src/linux_speech_flow/sounds.py` as an artifact path. The actual implementation placed play_sound() in `src/linux_speech_flow/sounds/__init__.py` — a valid auto-fix because Python cannot have both a `sounds.py` module and a `sounds/` package directory in the same parent. The import path `from linux_speech_flow.sounds import play_sound` is identical from callers' perspective. This is not a gap.

---

### Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|----------|
| `config.py` | `DEFAULT_CONFIG` | dict merge in load_config() | WIRED | `config = dict(DEFAULT_CONFIG); config.update(data)` confirmed |
| `audio.py` | `pulsectl.Pulse.sink_list()` | pulsectl context manager | WIRED | `with pulsectl.Pulse(...) as pulse: sinks = pulse.sink_list()` |
| `sounds/__init__.py` | `sounds/start.wav` | importlib.resources.files() | WIRED | `importlib.resources.files("linux_speech_flow.sounds").joinpath(sound_name)` |
| `sounds/__init__.py` | paplay system binary | subprocess.Popen | WIRED | `subprocess.Popen(cmd, stderr=subprocess.DEVNULL)` non-blocking |
| `notify.py` | notify-send binary | subprocess.run with -p | WIRED | `subprocess.run(["notify-send", "-p", ...])` |
| `recorder.py` | pasimple.PaSimple | PA_STREAM_RECORD context manager | WIRED | `with pasimple.PaSimple(pasimple.PA_STREAM_RECORD, ...)` |
| `recorder.py` | on_complete callback | GLib.idle_add | WIRED | `GLib.idle_add(self._on_complete, self._wav_path)` |
| `recorder.py` | threading.Event | stop_event.is_set() per chunk | WIRED | `while not self._stop_event.is_set():` |
| `hotkey.py` | `recorder.py` AudioRecorder | AudioRecorder.start() in _start_recording | WIRED | `self._recorder = AudioRecorder(...)` + `self._recorder.start(...)` |
| `hotkey.py` | `sounds/__init__.py` play_sound | play_sound() calls throughout | WIRED | start.wav in _start_recording; stop.wav in _on_recorder_complete and _stop_recording(cancel); error.wav in _on_recorder_error |
| `hotkey.py` | `notify.py` send_notification | send_notification() at recording start | WIRED | `self._notif_id = send_notification("Recording...")` |
| `hotkey.py` | GLib.idle_add | all GTK ops from pynput thread | WIRED | `GLib.idle_add(self._start_recording)` and `GLib.idle_add(self._stop_recording, False)` |
| `settings.py` | `audio.py` list_sinks() | _enumerate_sinks() method | WIRED | `from linux_speech_flow.audio import list_sinks; self._sinks = list_sinks()` |
| `app.py` | `hotkey.py` HotkeyManager | do_startup() | WIRED | `self._hotkey_manager = HotkeyManager(...)` + `self._hotkey_manager.start()` |
| `app.py` | GLib.idle_add mark_started | startup guard | WIRED | `GLib.idle_add(self._hotkey_manager.mark_started)` |

---

### Requirements Coverage

| Requirement | Plans | Description | Status | Evidence |
|-------------|-------|-------------|--------|----------|
| CORE-01 | 01, 04, 05 | User can hold F9 to begin audio recording | PARTIAL — see human verification | F9 keypress starts recording (verified). "Hold" model changed to "toggle" — F9 press starts, ESC stops. REQUIREMENTS.md marks as Complete but the UX contract changed. |
| CORE-02 | 01, 03, 04, 05 | User can release F9 to stop recording and trigger transcription pipeline | PARTIAL — see human verification | ESC stops recording instead of F9 release. Transcription pipeline stub in place (_on_recording_complete). REQUIREMENTS.md marks as Complete. |
| CORE-03 | 01, 03, 05 | Audio captured from selected input device via PulseAudio/PipeWire (pasimple) | SATISFIED | recorder.py uses pasimple.PaSimple(PA_STREAM_RECORD) with device_name from config; 16kHz mono s16le WAV output confirmed |
| CORE-04 | 01, 02, 04, 05 | Audible sound plays when recording starts and stops | SATISFIED | start.wav plays on F9 press in _start_recording; stop.wav plays in _on_recorder_complete (all normal stop paths); error.wav plays in _on_recorder_error |
| CORE-05 | 01, 04, 05 | App detects and surfaces error if no audio input device available | SATISFIED | PaSimpleError caught in recorder._record_loop; _on_recorder_error callback plays error.wav and sends "Microphone unavailable" notification; settings shows PulseError message if enumeration fails |

**REQUIREMENTS.md traceability:** All 5 Phase 2 requirements (CORE-01 through CORE-05) mapped to Phase 2 and marked Complete. No orphaned requirements.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `app.py:75-78` | `_on_recording_complete` prints and deletes WAV — Phase 2 stub | Info | Expected: Phase 3 replaces with transcription. Not a blocker. |
| `app.py:47` | `_build_placeholder_window` — placeholder main window | Info | Expected: Phase 4 adds tray icon. Variable name only, not a stub implementation. |
| `settings.py:59` | `placeholder-text` property on password entry | Info | GTK widget property for UI hint text, not a code stub. |

No blocker or warning anti-patterns found. All three items are either expected Phase 2 stubs explicitly documented for Phase 3 replacement, or false-positive string matches.

---

### Human Verification Required

#### 1. Confirm Toggle Mode as Permanent Interaction Model

**Test:** Review the hotkey interaction model and confirm it matches project intent.

**Context:** The original phase goal and CORE-01/CORE-02 requirements describe hold-to-record (F9 held = recording active, F9 released = stop). During Plan 05 human testing, hold-to-record was found impractical for longer dictation. The implementation was changed to toggle mode (press F9 to start, press ESC to stop), which was approved by the user during human verification in Plan 05.

**Expected:** Either:
- (a) Toggle mode (F9 start, ESC stop) is accepted as the permanent model — update CORE-01/CORE-02 descriptions and phase goal to reflect toggle behavior, then mark phase complete.
- (b) Hold-to-record should be restored — re-plan hotkey.py to restore WAITING state and on_release handler.

**Why human:** This is a UX model decision. The code is functionally complete and working for toggle mode. The REQUIREMENTS.md marks CORE-01/CORE-02 as Complete, but the requirement text still says "hold" and "release F9" respectively. A human must confirm whether the requirements are satisfied as-written or need updating.

---

### Gaps Summary

No implementation gaps found. All 13 artifacts exist, are substantive (not stubs), and are fully wired. All 15 key links verified. All 22 tests pass.

The single open item is a documentation/intent alignment question: REQUIREMENTS.md and the phase goal describe hold-to-record; the implementation delivers toggle mode. The implementation is complete and human-approved — this requires a human decision on whether to update the requirements text to match, or revert to hold-to-record.

---

### Test Suite

```
22 passed in 0.08s
```

All pre-existing tests pass. No regressions introduced by Phase 2.

---

### Commits Verified

| Commit | Plan | Description |
|--------|------|-------------|
| `069121b` | 02-01 | chore: pynput, pasimple deps and sounds package-data |
| `1fe26d5` | 02-01 | feat: Phase 2 config defaults and list_sinks() |
| `750b7eb` | 02-02 | feat: generate bundled WAV sound files |
| `4de8d47` | 02-02 | feat: sounds/__init__.py and notify.py |
| `45e5f3f` | 02-03 | feat: AudioRecorder with pasimple recording thread |
| `83cba6b` | 02-04 | feat: HotkeyManager push-to-talk state machine |
| `12ccb5f` | 02-04 | feat: Audio section in SettingsWindow |
| `f5bcee5` | 02-05 | feat: HotkeyManager wired into App.do_startup() (toggle mode) |

All 8 commits confirmed present in git log.

---

_Verified: 2026-02-19T15:30:00Z_
_Verifier: Claude (gsd-verifier)_
