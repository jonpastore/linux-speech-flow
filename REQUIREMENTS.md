# Requirements

## CONF — Configuration

- [x] **CONF-01**: First-run wizard collects Groq API key
- [x] **CONF-02**: Groq API key is validated against the Groq API before being accepted
- [x] **CONF-03**: User selects microphone from available PulseAudio/PipeWire sources
- [x] **CONF-04**: User can define a custom vocabulary list that persists across restarts
- [x] **CONF-05**: All settings saved to ~/.config/linux-speech-flow/config.json with 0600 permissions

## CORE — Audio Capture

- [x] **CORE-01**: Global F9 hotkey captured via pynput regardless of focused application
- [x] **CORE-02**: Audio recorded from configured microphone via pasimple when hotkey active
- [x] **CORE-03**: Audible start and stop chimes play on recording start and stop
- [x] **CORE-04**: Error notification shown when microphone is unavailable
- [x] **CORE-05**: WAV file produced and passed to on_recording_complete callback on stop

## TRANS — Transcription & Text Injection

- [ ] **TRANS-01**: Recorded audio is sent to Groq Whisper API (whisper-large-v3-turbo default) for transcription
- [ ] **TRANS-02**: Raw transcript is sent to Groq LLM (meta-llama/llama-4-scout-17b-16e-instruct) for post-processing (grammar fix, filler removal, punctuation)
- [ ] **TRANS-03**: Post-processing prompt includes active window title and application name as context
- [ ] **TRANS-04**: Post-processed text is pasted into the focused application via clipboard (xclip + xdotool ctrl+v; ctrl+shift+v for terminals)
- [ ] **TRANS-05**: If post-processing fails, raw Whisper transcript is pasted as fallback
- [ ] **TRANS-06**: User can define a custom vocabulary list that is included in the post-processing prompt
- [ ] **TRANS-07**: F10 reprocess hotkey — single failed WAV retries immediately; multiple failed WAVs open GTK selection dialog
- [ ] **TRANS-08**: Failed WAV files saved to ~/.local/share/linux-speech-flow/failed/ with timestamp filename on retry exhaustion; cleaned up on successful reprocess
- [ ] **TRANS-09**: Batch reprocess mode presents "Write all to file" or "Paste each into current window" choice before processing multiple recordings
- [ ] **TRANS-10**: Processing sound (one-shot on pipeline start) and success chime (on paste) are bundled WAV files, individually toggleable in settings
- [ ] **TRANS-11**: F9 pressed during active pipeline queues the new recording in FIFO order; user notified "Recording queued (N pending)"

## TRAY — System Tray

- [ ] **TRAY-01**: Application icon in system tray (AppIndicator3 or AyatanaAppIndicator3)
- [ ] **TRAY-02**: Tray icon state changes during recording and transcribing phases
- [ ] **TRAY-03**: Desktop notification on error (API failure, mic unavailable)
- [ ] **TRAY-04**: Tray menu: View Run Log, Settings, Quit

## HIST — Pipeline History

- [ ] **HIST-01**: Each transcription run stores timestamp, raw transcript, processed transcript, window context, duration
- [ ] **HIST-02**: Only 20 most recent runs retained in SQLite at ~/.local/share/linux-speech-flow/
- [ ] **HIST-03**: GTK run log window accessible from tray menu

## DIST — Distribution

- [ ] **DIST-01**: Installable via `apt install ./linux-speech-flow_*.deb` on Ubuntu 22.04+, Debian 12+, Pop!_OS 22.04+
- [ ] **DIST-02**: .deb bundles Python virtualenv (no system pip/Python modification required)
- [ ] **DIST-03**: XDG autostart .desktop entry launches app at login after install
- [ ] **DIST-04**: Installable via `pip install linux-speech-flow` from PyPI
- [ ] **DIST-05**: README documents required system dependencies (xdotool, xclip, x11-utils, libnotify-bin, wl-clipboard)
