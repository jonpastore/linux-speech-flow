# Feature Landscape

**Domain:** Linux voice dictation (push-to-talk, cloud-transcribed, context-aware)
**Researched:** 2026-02-18
**Overall Confidence:** MEDIUM-HIGH

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Hold-to-record, release-to-transcribe | Core interaction model. Every competitor (Voxtype, whisper-dictation, Wispr Flow, SuperWhisper) uses this. Users won't accept toggle-based or VAD-only modes as the primary UX. | Med | Must handle key-down/key-up at evdev or global hotkey level. F9 is the planned key. |
| Paste transcribed text into focused application | The whole point of the tool. nerd-dictation, Voxtype, VOXD, OpenWhispr all do this. Without it, you're just a clipboard copier. | Med | X11: `xdotool`. Wayland: `wtype` or `ydotool`. Must detect display server and use the right tool. Clipboard fallback (`xclip`/`wl-copy` + simulated Ctrl+V) is essential since GNOME Wayland blocks `wtype`. |
| System tray / indicator icon | Users need to know the app is running. Blurt, Voxtype, VOXD, Turbo Whisper, OpenWhispr all provide tray icons. On GNOME, this means `AppIndicator3` or status notifier via libappindicator. | Low | GNOME requires the AppIndicator extension or the newer StatusNotifier protocol. |
| Visual recording feedback | Users must know when they're recording. Turbo Whisper has a waveform orb. Blurt turns the indicator yellow. The macOS FreeFlow has an animated waveform overlay. Without visual feedback, users panic about whether recording started. | Med | Options: system tray icon change (simple), desktop notification (simplest), floating GTK overlay (matches macOS parity). Recommend tray icon state change for v1, floating overlay as stretch. |
| Groq API key setup / configuration | Users need to enter their API key. The macOS version has a setup wizard. groq_whisperer uses env vars. OpenWhispr has an in-app settings UI. For a desktop app, a first-run dialog or config file is expected. | Low | Config file at `~/.config/freeflow/config.yaml` or `config.json` + first-run GUI dialog. Store API key in file with restricted permissions (0600), not in plaintext config. |
| Microphone selection | Users with USB mics, headsets, or audio interfaces need to pick which device to use. The macOS version has this. nerd-dictation supports PulseAudio device selection. | Low | Use PulseAudio/PipeWire APIs to enumerate sources. Default to system default device. |
| Audio recording (good quality, correct format) | Must capture audio at quality suitable for Whisper (16kHz mono is what Groq downsamples to, but sending higher quality is fine). nerd-dictation uses `parec`/`sox`/`pw-cat`. Voxtype uses native Rust audio. | Med | Python options: `sounddevice` (PortAudio bindings), `pyaudio`, or subprocess to `parecord`/`pw-record`. Recommend `sounddevice` for simplicity and PipeWire compatibility. |
| LLM post-processing (filler word removal, grammar cleanup) | The macOS version does this and it's what makes the output usable vs raw Whisper. Wispr Flow, SuperWhisper, Voxtype, and VOXD all offer post-processing. Raw Whisper output has filler words, bad punctuation, and no formatting. | Low | Already designed in macOS version. Send raw transcript + context to Groq LLM (Llama). Same API, same prompts. Direct port. |
| Custom vocabulary | Technical terms, proper nouns, jargon. The macOS version has this. SuperWhisper, Willow, OpenWhispr, and Voxtype all support custom dictionaries. Users with specialized terminology will leave without it. | Low | Pass vocabulary list to the LLM post-processing prompt. Direct port from macOS. |
| Sound feedback (start/stop recording) | Audible confirmation that recording started and stopped. The macOS version plays system sounds. Without audio feedback, users don't know if the hotkey registered. | Low | Play a short sound file via `paplay`, `pw-play`, or Python `sounddevice`. Bundle two small WAV files. |
| Error handling with user-visible messages | When the API is down, key is invalid, or mic fails, the user needs to know. Every serious tool surfaces errors. | Low | Desktop notifications via `notify-send` or GTK dialog. |

## Differentiators

Features that set FreeFlow Linux apart from every other Linux dictation tool. Not expected in the ecosystem, but highly valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Context-aware post-processing (active app + window title) | **The killer feature.** No Linux dictation tool does this well. Wispr Flow's "deep context" is their premium differentiator on macOS. Vibevoice does screenshot+LLM but is a hack project. FreeFlow Linux would be the first polished Linux tool with context-aware dictation. Correctly spells names from emails, adapts tone for Slack vs docs, recognizes code context. | High | On Linux: get active window via `xdotool getactivewindow getwindowname` (X11) or `gdbus` / AT-SPI2 (Wayland). Get focused app name from `/proc`. Screenshot via `gnome-screenshot`, `grim` (Wayland), or D-Bus ScreenCast portal. The macOS version sends screenshot + app metadata to LLM for context inference. |
| Screenshot-based context (send screen to LLM) | Enables the LLM to see what the user sees: email recipients, code, document content. Only Vibevoice attempts this on Linux (using gnome-screenshot + Ollama). The macOS version captures the focused window and sends it as base64 JPEG to Groq's vision-capable model. | High | XDG Desktop Portal `org.freedesktop.portal.Screenshot` is the cross-DE way. Falls back to `gnome-screenshot -w` or `grim`. Must handle permission dialogs. Groq's Llama Scout supports vision. |
| Pipeline history / run log | Debug and review past transcriptions. The macOS version stores the last 20 runs with raw transcript, post-processed output, context, screenshot, and audio. No Linux competitor offers this. | Med | SQLite or JSON file in `~/.local/share/freeflow/`. Store: timestamp, raw transcript, processed transcript, context summary, audio file path. |
| Configurable hotkey | Most Linux tools hardcode the hotkey. The macOS version offers Fn, Right Command, etc. Letting users pick their own key is a quality-of-life differentiator. | Med | Need to support at least F9 (default) and a few alternatives. evdev-based key monitoring or global X11 keybind. |
| First-run setup wizard (GUI) | Most Linux dictation tools require manual config file editing or CLI setup. A polished GTK wizard that walks through API key entry, mic selection, and permissions is rare in this space. | Med | GTK4 or PyGObject dialog. 2-3 screens: API key, mic test, hotkey config. |
| Audio playback in run log | The macOS version lets you listen to recorded audio in the run log. Useful for debugging transcription errors. No Linux competitor does this. | Low | Store WAV files alongside history entries. Play with `sounddevice` or shell out to `paplay`. |

## Anti-Features

Features to explicitly NOT build for v1. These add complexity without proportional value, or conflict with the project's philosophy.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Local/offline Whisper transcription | The macOS version explicitly chose Groq cloud because local Whisper + local LLM = 5-10s latency vs <1s with Groq. Battery/CPU concerns on laptops. Adding faster-whisper/whisper.cpp as an option fractures the UX and doubles the testing surface. | Use Groq API exclusively. The free tier is generous. Mention local support as a future possibility. |
| Continuous/always-on dictation (VAD mode) | Voice Activity Detection mode (always listening) is complex, resource-hungry, and privacy-concerning. nerd-dictation and voice_typing support it, but push-to-talk is the core UX. Adding VAD mode adds significant complexity for a niche use case. | Stick to push-to-talk. It's simpler, more private, and matches the macOS reference. |
| Multi-provider API support (OpenAI, Anthropic, etc.) | OpenWhispr supports 6+ providers. This is a maintenance nightmare for v1. Groq provides the fastest inference (164x real-time), a free tier, and both Whisper + LLM APIs. One provider simplifies everything. | Use Groq only. Same provider for transcription (Whisper) and post-processing (Llama). |
| GUI settings window (full preferences panel) | The macOS version has a rich settings panel. For Linux v1, a config file + first-run wizard is sufficient. Building a full GTK preferences UI is high effort for settings that rarely change. | Config file (`~/.config/freeflow/config.yaml`) for advanced users. First-run wizard for initial setup. Settings panel is a v2 feature. |
| Auto-update mechanism | The macOS version checks GitHub releases and self-updates. On Linux, updates come via the package manager (apt, pip, etc.). Building a custom updater is pointless and potentially dangerous. | Distribute via pip, .deb, or AppImage. Let the ecosystem handle updates. |
| Wayland-first architecture | GNOME Wayland has fundamental limitations (no virtual keyboard protocol, wtype blocked). Pop!_OS (the target) ships X11 by default with COSMIC. Obsessing over Wayland purity for v1 wastes time. | Support X11 first (xdotool + xclip). Add Wayland fallbacks (ydotool, wl-copy) that work where possible. Full Wayland support is a v2 concern. |
| GNOME Shell extension approach | Blurt does this. Shell extensions break on every GNOME version update, are tied to one DE, and have a tiny API surface. A standalone app is more portable and maintainable. | Build as a standalone Python application with system tray integration. |
| Dictation modes / personas (email mode, code mode, etc.) | SuperWhisper and Wispr Flow offer modes that change post-processing behavior. Adds UX complexity. The context-aware pipeline already adapts to the active app automatically. | Let the context-awareness system handle adaptation implicitly. No user-facing mode switching needed. |
| Course correction / self-correction | Wispr Flow handles "actually, I meant..." mid-dictation. Requires sophisticated NLP and significantly complicates the post-processing pipeline. | Let the LLM handle minor self-corrections naturally in post-processing. Don't build explicit correction logic. |
| Translation support | Some tools offer real-time translation. Niche feature, adds complexity, not part of the macOS reference. | Whisper already handles multilingual input. The LLM can translate if the user asks in their dictation. No special feature needed. |
| Real-time streaming transcription | Showing words as they're spoken requires WebSocket streaming or a local model. Groq's API is batch-based. The push-to-talk model works fine without streaming. | Show "Transcribing..." status. The <1s Groq latency makes streaming unnecessary. |

## Feature Dependencies

```
API Key Setup --> Recording --> Transcription --> Post-Processing --> Paste
                                                       |
                                              Context Capture (parallel with recording)
                                                       |
                                              Screenshot Capture (optional, parallel)

System Tray --> Visual Recording Feedback
Config File --> Hotkey Setup --> Recording
Config File --> Microphone Selection --> Recording
Audio Storage --> Pipeline History --> Audio Playback
```

Key dependency chains:
- Recording depends on: microphone access, hotkey listener, audio library
- Transcription depends on: valid API key, recorded audio file
- Post-processing depends on: raw transcript, context (optional), vocabulary (optional)
- Paste depends on: xdotool/ydotool/wtype installed, display server detection
- Context capture should start in parallel with recording (same as macOS) to minimize latency
- Screenshot capture is optional and should degrade gracefully if permissions are denied

## MVP Recommendation

**Phase 1 - Core Pipeline (must ship):**
1. Hold F9 to record, release to transcribe+paste (the core loop)
2. Groq API transcription (Whisper large-v3)
3. LLM post-processing with basic context (app name, window title)
4. Paste into focused app via xdotool (X11)
5. Config file for API key and basic settings
6. Sound feedback on record start/stop
7. System tray icon with recording state indicator
8. Error notifications via notify-send

**Phase 2 - Parity with macOS:**
1. Screenshot-based context capture
2. Custom vocabulary support
3. Microphone selection
4. First-run setup wizard (GTK)
5. Pipeline history / run log
6. Configurable hotkey

**Phase 3 - Polish:**
1. Wayland support (ydotool/wtype fallbacks)
2. Audio playback in run log
3. Desktop notifications for transcription results
4. Launch at login (XDG autostart)
5. Packaging (.deb, pip, AppImage)

**Defer indefinitely:**
- Local Whisper: contradicts the speed-first design philosophy
- Multi-provider support: maintenance burden with no user demand
- Auto-update: let package managers handle it
- Full settings GUI: config file is fine for power users

## Sources

### Linux Dictation Tools (researched directly)
- [nerd-dictation](https://github.com/ideasman42/nerd-dictation) - Offline VOSK-based, hackable Python, X11/Wayland support (HIGH confidence)
- [Voxtype](https://voxtype.io/) - Rust-based, offline Whisper, X11/Wayland, GPU acceleration (MEDIUM confidence)
- [OpenWhispr](https://github.com/OpenWhispr/openwhispr) - Cross-platform, multi-provider, React/TypeScript (MEDIUM confidence)
- [Turbo Whisper](https://github.com/knowall-ai/turbo-whisper) - Waveform UI, SuperWhisper-like for Linux (MEDIUM confidence)
- [whisper-dictation](https://github.com/jacopone/whisper-dictation) - NixOS-focused, GTK4, local whisper.cpp (MEDIUM confidence)
- [VOXD](https://github.com/jakovius/voxd) - PyQt6, multi-DE support, AI post-processing (MEDIUM confidence)
- [groq_whisperer](https://github.com/KennyVaneetvelde/groq_whisperer) - Groq API, hold-key-to-record, clipboard (MEDIUM confidence)
- [voice_typing](https://github.com/themanyone/voice_typing) - Bash script, VAD-based, minimal (MEDIUM confidence)
- [Blurt](https://github.com/QuantiusBenignus/blurt) - GNOME Shell extension, whisper.cpp (LOW confidence)
- [Vibevoice](https://www.paepper.com/blog/posts/vibe-coding-update-voice-assistant-that-types-anywhere-with-screenshot-context/) - Screenshot context + Ollama LLM (LOW confidence)

### Commercial Competitors (feature reference)
- [Wispr Flow](https://wisprflow.ai/) - Context-aware, course correction, 100 languages, SOC2 (HIGH confidence)
- [SuperWhisper](https://superwhisper.com/) - Offline, custom modes, model selection (HIGH confidence)
- [Monologue](https://www.monologue.to/) - Deep context, mentioned in FreeFlow README (MEDIUM confidence)

### Ecosystem Analysis
- [AI Dictation Tool Comparison](https://afadingthought.substack.com/p/best-ai-dictation-tools-for-mac) - Philosophy comparison: mystery box vs transparent (MEDIUM confidence)
- [Groq Whisper API](https://console.groq.com/docs/speech-to-text) - 164x real-time speed, free tier (HIGH confidence)
- [Linux Mint Forums](https://forums.linuxmint.com/viewtopic.php?t=452621) - User frustrations with Linux dictation (MEDIUM confidence)
- [openSUSE Forums](https://forums.opensuse.org/t/dictation-voice-to-text-is-it-forgotten/46396) - "Voice dictation is forgotten on Linux" (MEDIUM confidence)
- [Wayland paste issues](https://github.com/OpenWhispr/openwhispr/issues/240) - xdotool fails silently on GNOME Wayland (HIGH confidence)
