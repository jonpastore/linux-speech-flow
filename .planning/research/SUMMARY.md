# Project Research Summary

**Project:** FreeFlow Linux — Python voice dictation system tray app
**Domain:** Linux desktop voice dictation (push-to-talk, cloud-transcribed, context-aware)
**Researched:** 2026-02-18
**Confidence:** MEDIUM-HIGH

## Executive Summary

FreeFlow Linux is a port of a macOS voice dictation app to Linux (targeting Pop!_OS/Ubuntu). The core product is a system tray app that lets users hold F9 to record audio, which is then transcribed via Groq Whisper and post-processed by a Groq LLM before being pasted into the active application. The Linux dictation tool landscape is weak — most competitors are offline/local-only, lack LLM post-processing, and have no context awareness. FreeFlow has a clear opportunity to be the first polished, cloud-speed Linux dictation tool, and the macOS reference implementation provides a strong feature specification.

The recommended approach is a Python app using PyGObject/AppIndicator3 for the system tray, pynput for global hotkeys, pasimple (not sounddevice) for audio recording, and the Groq SDK for transcription and LLM post-processing. The architecture is a GTK main thread for UI plus 2-3 daemon worker threads communicating via `queue.Queue` and `GLib.idle_add()` for thread-safe state updates. Text injection uses xclip + xdotool Ctrl+V (never `xdotool type`). The build order is configuration first, then individual components, then pipeline integration, then UI, then packaging — each phase independently testable.

Four pitfalls require architectural decisions before writing any code: (1) use pasimple instead of sounddevice/PyAudio because PortAudio 19.6.0 on Ubuntu cannot enumerate PulseAudio/PipeWire devices; (2) use clipboard paste exclusively because xdotool type breaks on any non-ASCII character; (3) handle both AppIndicator3 and AyatanaAppIndicator3 with a try/except pattern because different distros ship different forks; and (4) bundle a virtualenv inside the .deb using dh-virtualenv or fpm because PEP 668 prevents pip install into system Python on Ubuntu 24.04+. These are not optional — choosing wrong causes rewrites.

## Key Findings

### Recommended Stack

The stack is lean and purposeful. GTK 3.0 via PyGObject is non-negotiable for system tray support on GNOME — it is the only reliable approach and what tools like Slack and Discord use. pynput 1.8.1 handles global hotkeys cleanly via Xlib without requiring a GTK main loop. The audio recording decision is the most critical: PITFALLS.md contradicts STACK.md by recommending pasimple over sounddevice — pasimple talks PulseAudio directly and sidesteps the PortAudio version problem. Groq SDK 1.0.0 handles both Whisper transcription and Llama LLM post-processing through one API. Text injection is via subprocess calls to xclip + xdotool (system tools), not Python wrappers. Packaging uses fpm or dh-virtualenv for bundled .deb — not stdeb or naked pip.

**Core technologies:**
- Python 3.11+: runtime — matches Ubuntu 24.04 default, avoid 3.13 until ecosystem catches up
- PyGObject + AppIndicator3/AyatanaAppIndicator3: system tray — only reliable GNOME tray approach
- pynput 1.8.1: global hotkeys — X11-native via Xlib, clean on_press/on_release callbacks
- pasimple: audio recording — talks PulseAudio/PipeWire directly, avoids PortAudio version trap
- groq 1.0.0: Whisper transcription + Llama LLM post-processing — single API, 164x realtime speed
- xclip + xdotool (subprocess): text injection — clipboard paste pattern, never xdotool type
- keyring 25.7.0: API key storage — GNOME Keyring / KWallet, never plaintext config
- fpm 1.17.0 + dh-virtualenv: packaging — bundled venv in .deb, PEP 668 compliant
- uv: Python project management — fast, modern, lockfiles

**Critical version note:** sounddevice is listed in STACK.md but PITFALLS.md (higher specificity) overrides this — use pasimple instead. If sounddevice is used anyway, the .deb must bundle a custom-compiled PortAudio 19.7.0+.

### Expected Features

FreeFlow's feature landscape is well-researched across 10+ Linux competitors and 3 commercial tools. The macOS reference implementation provides the spec for most features.

**Must have (table stakes):**
- Hold-to-record, release-to-transcribe — core UX that all competitors use
- Paste transcribed text into focused application — the product's entire purpose
- System tray icon with recording state visual feedback — users must know app is running/recording
- Groq Whisper transcription — speed (164x realtime) is the product's competitive advantage
- LLM post-processing (filler words, grammar) — what separates FreeFlow from raw Whisper tools
- Config file for API key — minimum viable setup experience
- Sound feedback on record start/stop — critical for push-to-talk UX (did the hotkey register?)
- Error notifications via notify-send — user must know when API fails

**Should have (differentiators):**
- Context-aware post-processing (active window title + app name) — no Linux competitor does this well
- Screenshot-based context capture — only Vibevoice attempts this on Linux, macOS parity feature
- Pipeline history / run log — unique among Linux competitors, useful for debugging
- Configurable hotkey — most Linux tools hardcode their key
- First-run setup wizard (GTK) — rare quality in Linux dictation tools
- Custom vocabulary — technical terms, proper nouns

**Defer to v2+:**
- Wayland-first architecture — X11 is sufficient and Wayland breaks xdotool, xclip, pynput entirely
- Local/offline Whisper — contradicts speed-first design philosophy
- Multi-provider API support — maintenance burden, Groq free tier is generous
- Full settings GUI panel — config file is sufficient for v1 power users
- Auto-update mechanism — let apt/pip handle updates

### Architecture Approach

The architecture is a GTK main loop on the main thread with 2-3 daemon worker threads. The threading model is strict: GTK objects are only ever touched from the main thread via `GLib.idle_add()`; worker threads communicate via `queue.Queue`; blocking I/O (API calls, audio recording) happens on the pipeline worker thread only. The pipeline coordinator orchestrates the full record-transcribe-post-process-paste sequence as a queue consumer. Each component maps to a single module file. Asyncio is explicitly rejected — 2 HTTP calls per run don't justify the GTK/asyncio event loop conflict.

**Major components:**
1. AppIndicator3 TrayIcon — menu bar icon, recording state display, menu actions; GTK main thread only
2. HotkeyListener (pynput) — global key press/release as daemon thread; enqueues events, never does work
3. PipelineCoordinator — queue consumer daemon thread; orchestrates record->transcribe->process->paste
4. AudioRecorder (pasimple) — PulseAudio recording to WAV temp file; owned by coordinator
5. GroqWhisperClient + GroqLLMClient — blocking HTTP calls from worker thread; returns strings
6. TextPaster — xclip + xdotool subprocess; clipboard paste pattern with 500ms+ restore delay
7. StateManager — central state with observer callbacks; always updated via GLib.idle_add() from workers
8. ConfigManager — XDG-compliant JSON config at ~/.config/freeflow/config.json

**Build order (dependency-driven):** config -> recorder -> transcription + postprocessing -> paste -> hotkey -> pipeline + state -> tray + app -> packaging. Each phase is independently testable.

### Critical Pitfalls

1. **GNOME system tray requires AppIndicator extension** — the extension is NOT enabled by default on all Pop!_OS/Ubuntu installs. Use try/except import for AppIndicator3 vs AyatanaAppIndicator3 (different distros ship different forks). Declare the extension as a .deb dependency. Detect missing extension at startup and show a helpful dialog rather than silently failing.

2. **Audio library: use pasimple, not sounddevice** — PortAudio 19.6.0 (Ubuntu default) cannot enumerate PulseAudio/PipeWire devices. sounddevice.query_devices() returns empty or only raw ALSA devices on stock Ubuntu. pasimple bypasses PortAudio entirely and talks PulseAudio/PipeWire directly.

3. **Text injection: clipboard paste only, never xdotool type** — xdotool type breaks on any non-ASCII character (accented letters, curly quotes, em-dashes, emoji). Use xclip to set clipboard, then xdotool key --clearmodifiers ctrl+v. Add 500ms+ delay before restoring old clipboard to avoid race condition. Detect terminal emulators (Ctrl+Shift+V, not Ctrl+V).

4. **PEP 668 blocks pip on system Python (Ubuntu 24.04+)** — use dh-virtualenv or fpm with bundled virtualenv inside .deb. The .deb must be fully self-contained; never assume pip is available on the target system.

5. **Don't use systemd user service for autostart** — systemd services lack DISPLAY, DBUS_SESSION_BUS_ADDRESS, and XDG_RUNTIME_DIR. Use a .desktop file in /etc/xdg/autostart/ instead. This is the correct freedesktop way for GUI autostart.

## Implications for Roadmap

Based on combined research, the architecture's build-order dependency graph maps cleanly to a 5-phase roadmap:

### Phase 1: Core Pipeline (X11 MVP)
**Rationale:** The pipeline coordinator research defines a clear dependency order (config -> recorder -> transcription -> paste -> hotkey -> coordinator -> tray). This is the whole product. Everything else is polish or packaging.
**Delivers:** Working end-to-end dictation: hold F9, speak, release, text appears in active app.
**Features:** Hold-to-record, Whisper transcription, LLM post-processing (basic context), clipboard paste, tray icon, sound feedback, error notifications, API key in config file.
**Avoids:** sounddevice/PortAudio trap (use pasimple), xdotool type (use clipboard paste from day one), AppIndicator library conflict (try/except pattern from day one), terminal emulator paste bug (detect window class).
**Research flag:** LOW — patterns are well-documented. No additional research needed for this phase.

### Phase 2: macOS Feature Parity
**Rationale:** Once the core pipeline works, close the gap to macOS with screenshot context, custom vocabulary, mic selection, run log, configurable hotkey, and first-run wizard. These features are isolated from the core pipeline and can be added without rearchitecting.
**Delivers:** Full macOS feature parity. Context-aware dictation with screenshot. History log. User-friendly setup.
**Features:** Screenshot-based context capture (X11 via maim), custom vocabulary via LLM prompt, microphone selection, pipeline history (SQLite or JSON), configurable hotkey, first-run GTK wizard.
**Avoids:** Screenshot race condition (200-500ms delay post-focus-change on X11), Wayland screenshot complexity (defer to v3), hotkey grab conflict (make configurable, detect failure gracefully).
**Research flag:** MEDIUM — screenshot XDG portal vs maim decision needs validation. SQLite vs JSON for history log needs decision.

### Phase 3: Polish and Distribution
**Rationale:** Packaging and autostart are explicitly last because packaging decisions depend on which Python libraries were actually used (pasimple vs sounddevice changes .deb deps). PITFALLS.md is clear that PEP 668 requires a bundled venv — this is the entire packaging strategy.
**Delivers:** Installable .deb package. Launch at login. Desktop integration.
**Features:** .deb via dh-virtualenv/fpm with bundled venv, .desktop autostart (not systemd), XDG autostart, app icon, desktop launcher.
**Avoids:** PEP 668 / system Python conflict (bundled venv), systemd autostart environment problems (use .desktop), missing GNOME extension (declare as Depends in .deb).
**Research flag:** LOW — dh-virtualenv pattern is well-documented by Spotify. fpm is straightforward.

### Phase 4: Wayland Support (V2)
**Rationale:** Wayland breaks the entire X11 stack (xdotool, xclip, pynput via Xlib, Pillow ImageGrab). This requires different tools for every subsystem. Deferring to v2 lets v1 ship to the actual target (Pop!_OS default X11 session) without the Wayland complexity.
**Delivers:** Full functionality on GNOME Wayland, KDE Wayland.
**Features:** ydotool or wl-clipboard for paste, evdev for global hotkeys, grim or xdg-portal for screenshots, wl-copy for clipboard.
**Avoids:** Wayland paste silently failing (GNOME Wayland blocks xdotool), non-interactive screenshot limitation (use xdg-portal with acceptable dialog UX).
**Research flag:** HIGH — Wayland hotkey mechanism (evdev vs libei vs portal), evdev permissions model, and ydotool reliability all need deeper research.

### Phase Ordering Rationale

- Phases 1-3 are strictly X11 which matches the target platform (Pop!_OS ships X11 by default).
- Phase 1 completes before any packaging because library choices (audio, tray) affect .deb dependencies.
- The pitfalls research explicitly flags that audio library and text injection decisions must be made before writing code — Phase 1 forces these decisions first.
- Screenshot context (Phase 2) is isolated from the core pipeline and can be added without breaking Phase 1 code.
- Wayland (Phase 4) requires different implementations of hotkey, paste, clipboard, and screenshot — it is a parallel implementation track, not an incremental addition.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** Screenshot capture mechanism — xdg-desktop-portal vs maim vs scrot, timing requirements post-focus-change, whether Pillow ImageGrab is reliable enough or subprocess to maim is preferred.
- **Phase 2:** History log storage — SQLite (queryable, structured) vs JSON file (simpler, grep-able). Need a decision with rationale.
- **Phase 4:** Wayland hotkey mechanism — evdev requires input group membership, libei is newer but less mature, XDG Input Capture portal is not finalized. High uncertainty.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Core pipeline architecture is well-documented with code examples in ARCHITECTURE.md. GTK+queue+GLib.idle_add is a standard pattern. No additional research needed.
- **Phase 3:** dh-virtualenv + fpm packaging is a documented, production-proven pattern (Spotify, Sentry). .desktop autostart is standard freedesktop. No research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core libraries confirmed with current PyPI versions. Audio library recommendation conflicts between STACK.md (sounddevice) and PITFALLS.md (pasimple) — PITFALLS wins, but pasimple is less documented. |
| Features | HIGH | 10+ open source competitors analyzed, 3 commercial tools, user forum posts. Feature set is well-validated against market. |
| Architecture | HIGH | PyGObject threading guide is official. GTK+queue+GLib.idle_add is a proven pattern with code examples. Phase build order is dependency-driven. |
| Pitfalls | HIGH | Most critical pitfalls (PortAudio, xdotool Unicode, AppIndicator, PEP 668) confirmed via multiple GitHub issues and official documentation. Not speculative. |

**Overall confidence:** HIGH for Phase 1 and 3. MEDIUM for Phase 2. LOW for Phase 4 (Wayland).

### Gaps to Address

- **pasimple vs sounddevice:** PITFALLS.md makes a strong case for pasimple but it is a smaller library. Validate pasimple is actively maintained and has sufficient API for mic selection, device enumeration, and level metering before committing.
- **AppIndicator extension pre-installation:** PITFALLS.md says the extension is NOT enabled by default on Pop!_OS; STACK.md says it IS pre-installed. Need to test on a fresh Pop!_OS install to determine the actual default state.
- **Phase 2 context capture timing:** The macOS app captures context at key-down (parallel with recording). Linux implementation must decide: capture active window name + screenshot at key-down start, or at key-up before transcription. Timing matters for accuracy.
- **Fn key vs F9 behavior:** On many laptops, F9 requires Fn modifier. The hotkey must be configurable from day one. The first-run wizard should include a "press your hotkey" capture dialog.

## Sources

### Primary (HIGH confidence)
- [sounddevice docs](https://python-sounddevice.readthedocs.io/) — recording patterns, PortAudio requirements
- [pynput docs](https://pynput.readthedocs.io/) — keyboard listener threading model
- [PyGObject threading guide](https://pygobject.gnome.org/guide/threading.html) — GTK thread safety rules
- [GLib main loop docs](https://docs.gtk.org/glib/main-loop.html) — GLib.idle_add thread safety
- [Groq Whisper API docs](https://console.groq.com/docs/speech-to-text) — 164x realtime, whisper-large-v3
- [PEP 668 spec](https://peps.python.org/pep-0668/) — externally managed environment policy
- [dh-virtualenv by Spotify](https://github.com/spotify/dh-virtualenv) — bundled venv in .deb
- [gnome-shell-extension-appindicator](https://github.com/ubuntu/gnome-shell-extension-appindicator) — GNOME tray support
- [xdotool issue #154](https://github.com/jordansissel/xdotool/issues/154) — Unicode injection breakage
- [python-sounddevice issue #609](https://github.com/spatialaudio/python-sounddevice/issues/609) — PipeWire device enumeration failure
- [OpenWhispr issue #240](https://github.com/OpenWhispr/openwhispr/issues/240) — clipboard race condition timing

### Secondary (MEDIUM confidence)
- [nerd-dictation](https://github.com/ideasman42/nerd-dictation) — Linux dictation architecture reference
- [VOXD](https://github.com/jakovius/voxd) — Linux voice dictation multi-DE patterns
- [Vibevoice blog](https://www.paepper.com/blog/posts/vibe-coding-update-voice-assistant-that-types-anywhere-with-screenshot-context/) — screenshot+LLM context on Linux
- [fpm docs](https://fpm.readthedocs.io/) — .deb packaging from directory tree
- [XDG Base Directory ArchWiki](https://wiki.archlinux.org/title/XDG_Base_Directory) — directory conventions
- [pasimple](https://github.com/henrikschnor/pasimple) — PulseAudio Simple API Python wrapper

### Tertiary (LOW confidence)
- [Wispr Flow](https://wisprflow.ai/) — commercial context-aware dictation feature reference (inferred features from marketing)
- [OpenWhispr](https://github.com/OpenWhispr/openwhispr) — multi-provider architecture reference (TypeScript, not Python)

---
*Research completed: 2026-02-18*
*Ready for roadmap: yes*
