# Linux Speech Flow

> Speech-to-text for Linux. Hold a key, speak, release — text appears where you're typing.

[![CI](https://img.shields.io/github/actions/workflow/status/jonpastore/linux-speech-flow/ci.yml?branch=main&label=CI)](https://github.com/jonpastore/linux-speech-flow/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<!-- Screenshot -->
<!-- ![Screenshot](docs/screenshot.png) -->

## Features

- **Instant transcription** — press a hotkey, speak, release — text pastes where you're typing
- **Groq Whisper API** — fast, accurate speech-to-text (whisper-large-v3-turbo)
- **LLM post-processing** — grammar cleanup and filler word removal
- **Conversation mode** — long-form recording with AI analysis and Q&A
- **Multi-provider AI** — Groq, Grok by xAI, Google Gemini
- **Slack integration** — record huddles, post transcriptions to Slack channels
- **System tray** — always accessible, minimal footprint
- **Hotkey customization** — remap all hotkeys from Settings
- **Pipeline history** — last 20 runs with SQLite storage

## System Requirements

- Ubuntu 22.04+ / Debian 12 / Pop!_OS 22.04 (or compatible)
- Python 3.10+
- GTK 4 (libgtk-4-1)
- PulseAudio or PipeWire
- X11 or Wayland with XWayland
- `xdotool` (for text injection on X11)

## Installation

### From .deb package (recommended)

Download the latest `.deb` from [Releases](https://github.com/jonpastore/linux-speech-flow/releases):

```bash
sudo apt install ./linux-speech-flow_*.deb
```

### From PyPI

```bash
pip install linux-speech-flow
```

System dependencies must be installed separately (the `.deb` pulls these in automatically; the pip path does not):

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 libgirepository1.0-dev \
  libpulse-dev xdotool xclip libnotify-bin
```

## Quick Start

1. Run `linux-speech-flow`
2. The setup wizard opens on first launch
3. Enter your Groq API key ([get one free](https://console.groq.com/))
4. Select your microphone
5. Press the hotkey (default: `Ctrl+Alt+R`) to start recording — release to transcribe

**Autostart at login** is enabled automatically — the app writes
`~/.config/autostart/linux-speech-flow.desktop` on first run, so it starts with your
desktop session. Remove that file to disable it.

## Privacy

Audio is processed by Groq's Whisper API. Conversation transcripts sent for AI analysis go to
your chosen provider (Groq, Grok by xAI, or Google Gemini). No audio or transcription data is
stored by the app beyond what you save locally. Your API keys are stored in
`~/.config/linux-speech-flow/config.json` (mode 0600, readable only by you).

## API Keys

| Service | Required for | Get key |
|---------|-------------|---------|
| [Groq](https://console.groq.com/) | Transcription (required) | console.groq.com |
| [Grok by xAI](https://console.x.ai/) | Conversation AI (optional) | console.x.ai |
| [Google Gemini](https://aistudio.google.com/apikey) | Conversation AI (optional) | aistudio.google.com |
| [Slack](https://api.slack.com/apps) | Slack integration (optional) | See Slack setup guide below |

## Configuration

Config file: `~/.config/linux-speech-flow/config.json` (created on first run)

See [config.example.json](config.example.json) for all available options with placeholder values.

## Slack Setup

Slack integration requires creating a Slack App with specific bot scopes. See the
[Slack setup guide](docs/slack-setup.md) for step-by-step instructions.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT — see [LICENSE](LICENSE).
