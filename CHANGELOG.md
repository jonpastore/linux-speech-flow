# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-04

### Added
- Core speech-to-text pipeline: press hotkey, speak, release — text pasted to focused window
- Groq Whisper API transcription (whisper-large-v3-turbo model)
- LLM post-processing via Groq for grammar cleanup and filler word removal
- System tray with state icons (idle, recording, processing, error)
- GTK 4 setup wizard with API key validation and microphone selection
- First-run onboarding dialog with privacy disclosure
- Conversation mode: long-form recording with AI analysis and Q&A
- Conversation AI support: Groq, Grok by xAI, Google Gemini
- Slack huddle integration: record system audio + mic, post analysis to Slack
- Voice command activation in Slack huddles
- Hotkey customization via Settings dialog
- Pipeline history (SQLite, last 20 runs) with history window
- .deb package for Ubuntu/Debian/Pop!_OS
- History database stored with 0600 permissions (readable only by owner)
