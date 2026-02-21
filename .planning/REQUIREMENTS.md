# Requirements: Linux Speech Flow

**Defined:** 2026-02-18
**Core Value:** Hold a key, speak, release — transcribed text appears in whatever you're typing in.

## v1 Requirements

### Core Recording

- [x] **CORE-01**: User can press F9 to begin audio recording (toggle mode)
- [x] **CORE-02**: User can press ESC to stop recording and trigger transcription pipeline
- [x] **CORE-03**: Audio is captured from the selected input device via PulseAudio/PipeWire (pasimple)
- [x] **CORE-04**: Audible sound plays when recording starts and when it stops
- [x] **CORE-05**: App detects and surfaces an error if no audio input device is available

### Transcription & Post-Processing

- [x] **TRANS-01**: Recorded audio is sent to Groq Whisper API (whisper-large-v3) for transcription
- [x] **TRANS-02**: Raw transcript is sent to Groq LLM (meta-llama/llama-4-scout-17b-16e-instruct) for post-processing (grammar fix, filler removal, punctuation)
- [x] **TRANS-03**: Post-processing prompt includes active window title and application name as context
- [x] **TRANS-04**: Post-processed text is pasted into the focused application via clipboard (xclip + xdotool ctrl+v)
- [x] **TRANS-05**: If post-processing fails, raw Whisper transcript is pasted as fallback
- [x] **TRANS-06**: User can define a custom vocabulary list that is included in the post-processing prompt

### System Tray & Feedback

- [x] **TRAY-01**: Application icon appears in system tray on launch (AppIndicator3/AyatanaAppIndicator3 with dual-library fallback)
- [x] **TRAY-02**: Tray icon changes state visually during recording and transcribing phases
- [x] **TRAY-03**: Desktop notification appears on error (API failure, mic unavailable, etc.) via libnotify/notify-send
- [x] **TRAY-04**: Tray menu includes: View Run Log, Settings, Quit

### Configuration & Setup

- [x] **CONF-01**: On first launch, GTK setup wizard prompts user to enter Groq API key and validates it
- [x] **CONF-02**: Setup wizard allows user to select microphone from available PulseAudio/PipeWire sources
- [x] **CONF-03**: Settings are persisted to ~/.config/linux-speech-flow/config.json with 0600 permissions
- [x] **CONF-04**: User can edit custom vocabulary list via settings (stored in config.json)
- [x] **CONF-05**: User can select microphone from tray menu or settings (re-enumerates available sources)

### Pipeline History

- [x] **HIST-01**: Each transcription run is stored locally: timestamp, raw transcript, processed transcript, window context, duration
- [x] **HIST-02**: Up to 20 most recent runs are retained (SQLite in ~/.local/share/linux-speech-flow/)
- [ ] **HIST-03**: User can view run log as a GTK window launched from tray menu

### Distribution

- [ ] **DIST-01**: App is packaged as a .deb file installable via `apt install ./linux-speech-flow_*.deb` on Ubuntu 22.04+, Debian 12+, Pop!_OS 22.04+
- [ ] **DIST-02**: .deb bundles Python virtualenv (dh-virtualenv or fpm) to avoid PEP 668 system Python conflicts
- [ ] **DIST-03**: .deb postinst installs XDG autostart .desktop entry for launch at login
- [ ] **DIST-04**: App is installable via pip from PyPI (`pip install linux-speech-flow`)
- [ ] **DIST-05**: README documents required system dependencies (xdotool, xclip, libnotify-bin, gnome-shell-extension-appindicator)

## v2 Requirements

### Context (Screenshot)

- **CTX-01**: Screenshot of focused window is captured at recording start and sent to Groq LLM for deeper context inference
- **CTX-02**: Screenshot capture uses XDG Desktop Portal on Wayland, X11 screenshot on X11

### Hotkey

- **HOT-01**: User can configure the hold-to-record hotkey (default F9) from setup wizard or settings

### Wayland

- **WAY-01**: Text injection works on Wayland via wl-clipboard + wtype/ydotool fallback
- **WAY-02**: Global hotkey works on Wayland via evdev/libei

### Polish

- **POL-01**: Audio playback of recorded audio in run log (replay what was recorded)
- **POL-02**: Full settings GTK window (not just first-run wizard) for modifying all settings post-setup

## Out of Scope

| Feature | Reason |
|---------|--------|
| Local/offline Whisper | Kills the <1s latency advantage; defeats the purpose of using Groq |
| Multi-provider API support | Maintenance burden; Groq provides both Whisper + LLM in one place |
| Always-on VAD mode | Privacy concerns, resource-heavy; push-to-talk is the UX model |
| Auto-update mechanism | Linux users update via apt/pip; self-updater is pointless on Linux |
| macOS support | Existing Swift app handles that; this is a Linux-only codebase |
| Windows support | Not a target platform |
| Full settings GUI panel (v1) | Config file sufficient for v1; reduces scope significantly |
| Dictation modes/personas | Context-awareness handles this implicitly |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONF-01 | Phase 1 | Complete |
| CONF-02 | Phase 1 | Complete |
| CONF-03 | Phase 1 | Complete |
| CONF-04 | Phase 1 | Complete |
| CONF-05 | Phase 1 | Complete |
| CORE-01 | Phase 2 | Complete |
| CORE-02 | Phase 2 | Complete |
| CORE-03 | Phase 2 | Complete |
| CORE-04 | Phase 2 | Complete |
| CORE-05 | Phase 2 | Complete |
| TRANS-01 | Phase 3 | Complete |
| TRANS-02 | Phase 3 | Complete |
| TRANS-03 | Phase 3 | Complete |
| TRANS-04 | Phase 3 | Complete |
| TRANS-05 | Phase 3 | Complete |
| TRANS-06 | Phase 3 | Complete |
| TRAY-01 | Phase 4 | Complete |
| TRAY-02 | Phase 4 | Complete |
| TRAY-03 | Phase 4 | Complete |
| TRAY-04 | Phase 4 | Complete |
| HIST-01 | Phase 5 | Complete |
| HIST-02 | Phase 5 | Complete |
| HIST-03 | Phase 5 | Pending |
| DIST-01 | Phase 6 | Pending |
| DIST-02 | Phase 6 | Pending |
| DIST-03 | Phase 6 | Pending |
| DIST-04 | Phase 6 | Pending |
| DIST-05 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-19 after 01-03 (CONF-01 complete: validate_api_key implemented)*
