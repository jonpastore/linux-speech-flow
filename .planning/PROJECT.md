# FreeFlow Linux

## What This Is

FreeFlow Linux is an open source Python rewrite of FreeFlow — a voice dictation app — targeting Pop!_OS, Ubuntu, and Debian. The user presses and holds a hotkey (F9 by default) to record audio, which is transcribed via Groq Whisper, cleaned up via Groq LLM post-processing with context awareness, and pasted directly into the focused application.

## Core Value

Hold a key, speak, release — transcribed text appears in whatever you're typing in.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] System tray presence (DE-appropriate approach TBD by research)
- [ ] Hold F9 to record audio, release to transcribe and paste
- [ ] Audio captured via PulseAudio/PipeWire
- [ ] Transcription via Groq Whisper API (whisper-large-v3)
- [ ] Post-processing via Groq LLM with active app name + screenshot context
- [ ] Text injected into focused application via xdotool (X11)
- [ ] Groq API key setup flow on first launch
- [ ] Settings: hotkey selection, microphone selection, custom vocabulary
- [ ] Pipeline history (last 20 transcriptions)
- [ ] Launch at login (systemd user service)
- [ ] Packaged as installable .deb for Pop!_OS/Ubuntu/Debian

### Out of Scope

- macOS support — existing Swift app handles that
- Wayland support — X11 first; Wayland deferred to follow-on
- Windows support — not a target
- In-app auto-update — users update via apt or GitHub releases
- Mobile — not applicable

## Context

The Mac version (Swift/SwiftUI/AppKit) is the reference implementation in this repo. The Linux version is a behavioral port: same pipeline, same Groq API calls, same user experience — different language and system APIs.

**Mac → Linux mapping:**
- MenuBarExtra → System tray (approach TBD: AppIndicator3, ewmh, or GTK widget)
- AVFoundation audio → sounddevice (PulseAudio/PipeWire via PortAudio)
- Carbon hotkey → pynput or python-xlib global key grab (X11)
- Accessibility text insertion → xdotool type (X11)
- CoreData → SQLite (via sqlite3 stdlib) or JSON file
- UserDefaults → XDG config file (~/.config/freeflow/settings.json)
- ServiceManagement → systemd user service unit
- Keychain → libsecret / plaintext XDG config (600 permissions)
- ScreenCaptureKit → scrot or PIL/Xlib screenshot (X11)

**GNOME tray concern:** GNOME 40+ (Pop!_OS default) doesn't support AppIndicator natively. Research phase will determine the best approach — likely requiring either the Ubuntu AppIndicators GNOME extension or an alternative tray mechanism.

**Separate repo:** The Linux version will be published as its own open source repository (fork/sibling to zachlatta/freeflow). This repo serves as reference.

## Constraints

- **Platform**: Linux only (Debian/Ubuntu/Pop!_OS) — no cross-platform abstraction needed
- **Display server**: X11 only for v1 — Wayland text injection is not standardized
- **Language**: Python — chosen for ecosystem fit (sounddevice, PyGObject, xdotool bindings)
- **API**: Groq only — same as Mac version (whisper-large-v3 + llama-4-scout post-processing)
- **Distribution**: .deb package — must install cleanly with `apt install ./freeflow_*.deb`

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Python over Rust/Go | Fastest path to working .deb; good ecosystem for audio/GTK/xdotool | — Pending |
| X11 first, Wayland deferred | xdotool text injection doesn't work on Wayland; Wayland lacks standardized APIs | — Pending |
| F9 as default hotkey | Uncommon function key, rarely conflicts with system or app shortcuts | — Pending |
| System tray approach | Research phase will determine GTK/AppIndicator vs alternative for GNOME compat | — Pending |
| Separate Linux repo | Clean separation from Mac-specific codebase; better discoverability for Linux users | — Pending |

---
*Last updated: 2026-02-18 after initialization*
