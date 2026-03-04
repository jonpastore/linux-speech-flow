# Roadmap: linux-speech-flow

## Overview

linux-speech-flow is a multi-phase build from configuration skeleton to installable .deb package. The pipeline follows a strict dependency chain: config management enables audio recording, which feeds transcription, which feeds the system tray application shell, which gets history logging and conversation mode, and finally packaging wraps everything into an installable artifact. Each phase delivers a testable vertical slice — by Phase 3's completion, the core product works end-to-end.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation & Configuration** - Project scaffolding, config persistence, API key setup wizard, and microphone/vocabulary settings
- [x] **Phase 2: Audio Capture & Hotkey** - Toggle recording via Ctrl+Alt+R with pasimple audio recording, sound feedback, and device error handling
- [x] **Phase 3: Transcription & Text Injection** - Groq Whisper transcription, LLM post-processing with context, clipboard paste into focused app (completed 2026-02-21)
- [x] **Phase 4: System Tray & Desktop Integration** - AppIndicator tray icon with state feedback, menu actions, and desktop notifications
- [x] **Phase 5: Pipeline History** - SQLite run log storage, retention policy, and GTK history viewer (completed 2026-02-21)
- [x] **Phase 6: Conversation Mode** - Long-form recording, silence-chunked transcription, multi-provider AI analysis, iterative Q&A, coalesced file output (completed 2026-02-21)
- [x] **Phase 6.1: Conversation Status Enhancements** - Live silence timer and last-chunk transcript display in ConversationStatusWindow (completed 2026-03-03)
- [x] **Phase 7: Hotkey Customization** - Configurable hotkeys in Settings, key combination support (completed 2026-03-04)
- [ ] **Phase 8: Slack Integration** - Output to Slack, join Slack huddles as a bot; huddle end triggers transcription pipeline
- [ ] **Phase 8.1: Help Dialog** - Comprehensive in-app help window with feature explanations and hotkey reference
- [ ] **Phase 9: Packaging & Distribution** - .deb with bundled venv, XDG autostart, PyPI publishing, and dependency documentation

## Phase Details

### Phase 1: Foundation & Configuration
**Goal**: User can install dependencies, launch the app, complete first-run setup, and have all settings persisted for subsequent launches
**Depends on**: Nothing (first phase)
**Requirements**: CONF-01, CONF-02, CONF-03, CONF-04, CONF-05
**Success Criteria** (what must be TRUE):
  1. User launches app for the first time and sees a GTK setup wizard prompting for Groq API key
  2. Setup wizard validates the API key against Groq API before accepting it
  3. User can select a microphone from a list of available PulseAudio/PipeWire sources in the wizard
  4. User can define and edit a custom vocabulary list that persists across restarts
  5. All settings are saved to ~/.config/linux-speech-flow/config.json with 0600 permissions and survive app restart
**Plans**: 5 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffold, Gtk.Application entry point, audio device enumeration
- [x] 01-02-PLAN.md — Config persistence TDD (load/save/permissions/vocabulary/setup_complete)
- [x] 01-03-PLAN.md — Groq API key validation TDD (format check + live HTTP, mocked tests)
- [x] 01-04-PLAN.md — GTK wizard (Gtk.Stack), settings window, app startup sequence
- [x] 01-05-PLAN.md — Human verification of complete Phase 1 wizard flow

### Phase 2: Audio Capture & Hotkey
**Goal**: User can press Ctrl+Alt+R to toggle recording from their microphone and hear audible feedback confirming recording start/stop
**Depends on**: Phase 1
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05
**Success Criteria** (what must be TRUE):
  1. User presses Ctrl+Alt+R and audio recording begins immediately from the configured microphone via pasimple
  2. User presses Ctrl+Alt+R again (or ESC) and audio recording stops, producing a WAV file ready for transcription
  3. Audible start and stop sounds play when recording begins and ends
  4. If no audio input device is available, user sees a clear error message
  5. Global hotkey works regardless of which application is focused (X11 key grab)
**Plans**: 5 plans

Plans:
- [x] 02-01-PLAN.md — Package deps (pynput, pasimple), config Phase 2 defaults, audio.list_sinks()
- [x] 02-02-PLAN.md — Bundled WAV sound files + sounds.py (paplay) + notify.py (notify-send)
- [x] 02-03-PLAN.md — AudioRecorder: pasimple recording thread, RMS silence detection, WAV lifecycle
- [x] 02-04-PLAN.md — HotkeyManager: pynput toggle-record state machine (Ctrl+Alt+R start/stop, ESC stop) + Settings Audio section
- [x] 02-05-PLAN.md — App.do_startup() wiring + human verification of complete Phase 2 flow

### Phase 3: Transcription & Text Injection
**Goal**: User presses Ctrl+Alt+R to start recording; on stop the transcribed, cleaned-up text appears in whatever application they were typing in
**Depends on**: Phase 2
**Requirements**: TRANS-01, TRANS-02, TRANS-03, TRANS-04, TRANS-05, TRANS-06, TRANS-07, TRANS-08, TRANS-09, TRANS-10, TRANS-11
**Success Criteria** (what must be TRUE):
  1. Recorded audio is sent to Groq Whisper API and raw transcript returned
  2. Raw transcript is post-processed by Groq LLM with active window title and application name as context
  3. Post-processed text is pasted into the focused application via xclip + xdotool Ctrl+V (Ctrl+Shift+V for terminals)
  4. If LLM post-processing fails, raw Whisper transcript is pasted as fallback
  5. Custom vocabulary words from config are included in the post-processing prompt
  6. Processing sound plays on pipeline start; success chime plays on paste
  7. Ctrl+Alt+R during active pipeline queues the recording with user notification
  8. Ctrl+Alt+P retries failed WAVs (single: immediate; multiple: GTK dialog with batch mode)
**Plans**: 6 plans

Plans:
- [x] 03-01-PLAN.md — Config Phase 3 defaults + processing.wav/success.wav + groq dep + REQUIREMENTS.md
- [x] 03-02-PLAN.md — transcription.py (TranscriptionPipeline) + window_context.py + injector.py
- [x] 03-03-PLAN.md — Transcription settings section in SettingsWindow (LLM model, timeout, sounds, categories, prompt editor)
- [x] 03-04-PLAN.md — App._on_recording_complete wiring + HotkeyManager F10 dispatch + queue notification
- [x] 03-05-PLAN.md — ReprocessDialog GTK4 modal + TranscriptionPipeline.submit_batch_to_file()
- [x] 03-06-PLAN.md — Pre-verification checks + human verification of complete Phase 3 flow

### Phase 4: System Tray & Desktop Integration
**Goal**: User sees linux-speech-flow as a persistent system tray application with visual recording state, menu actions, and error notifications
**Depends on**: Phase 3
**Requirements**: TRAY-01, TRAY-02, TRAY-03, TRAY-04
**Success Criteria** (what must be TRUE):
  1. Application icon appears in the system tray on launch (trayer/StatusNotifierItem — AppIndicator3 is GTK3-only, incompatible with GTK4)
  2. Tray icon visually changes state during recording and transcribing phases (animated frame-swapping)
  3. Desktop notification appears when an error occurs (API failure, mic unavailable)
  4. Tray menu includes Settings, Open Debug Log, Reprocess Failed (N), and Quit options that each work correctly
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md — Create icons/ package (8 SVGs) + tray.py TrayManager + pyproject.toml (trayer dep)
- [x] 04-02-PLAN.md — Wire HotkeyManager/TranscriptionPipeline callbacks + headless app.py + XDG autostart
- [x] 04-03-PLAN.md — Pre-checks + human verification of all 8 tray scenarios

### Phase 04.1: FreeFlow Rename and Codebase Cleanup (INSERTED)

**Goal:** Rename all FreeFlow/freeflow branding to Linux Speech Flow throughout the codebase, clean up installed artifacts, add legacy config migration, and squash git history to a single clean initial commit
**Depends on:** Phase 4
**Plans:** 3/3 plans complete

Plans:
- [x] 04.1-01-PLAN.md — Rename 8 SVG icons (git mv), update tray.py constants + install_icons() cleanup, update app.py strings + autostart cleanup
- [x] 04.1-02-PLAN.md — Config migration in config.py, dead code scan in settings.py, REQUIREMENTS.md update
- [x] 04.1-03-PLAN.md — Git history squash to single commit + human verification

### Phase 5: Pipeline History
**Goal**: User can review their recent transcription history with full context in a dedicated log viewer
**Depends on**: Phase 3
**Requirements**: HIST-01, HIST-02, HIST-03
**Success Criteria** (what must be TRUE):
  1. Each transcription run stores timestamp, raw transcript, processed transcript, window context, and duration
  2. Only the N most recent runs are retained in SQLite at ~/.local/share/linux-speech-flow/ (N configurable, default 20)
  3. User can open a GTK run log window from the tray menu showing all stored runs with their details
**Plans**: 4 plans

Plans:
- [x] 05-01-PLAN.md — HistoryStore (SQLite, WAL mode, insert+prune, extensible schema) + config defaults
- [x] 05-02-PLAN.md — HistoryWindow GTK class (expandable rows, copy buttons, live updates, size persistence)
- [x] 05-03-PLAN.md — Integration wiring: transcription.py + app.py + tray menu item + settings Maintenance section
- [x] 05-04-PLAN.md — Pre-verification checks + human verification of complete history feature

### Phase 6: Conversation Mode
**Goal**: User can record long-form conversations (calls, huddles, brain-dumps) and get a fully transcribed, AI-analyzed output file with iterative Q&A for requirements/action item extraction
**Depends on**: Phase 5
**Requirements**: CONV-01, CONV-02, CONV-03, CONV-04, CONV-05
**Success Criteria** (what must be TRUE):
  1. User presses Ctrl+Alt+C to start/stop a long-form conversation recording (silence-chunked, auto-transcribed per chunk)
  2. Auto-stop triggers: 180s silence prompts user, 300s auto-stops with audio cue; max 4hr hard limit with warning sound; all timers configurable
  3. Post-stop dialog lets user save to file, inject to active window, or both; AI analysis optional per session with auto-analyze setting
  4. Coalesced output file: ISO8601+AI-title.txt with AI summary → Q&A rounds → full transcript
  5. AI iterative Q&A loop (configurable API: Groq/Grok/Gemini) continues until 95% confidence or max iterations; user answers by speaking or typing
**Plans**: 8 plans

Plans:
- [x] 06-01-PLAN.md — Foundation: Phase 6 config defaults, openai/google-genai deps, HotkeyManager Ctrl+Alt+C/F bindings, tray badge SVGs
- [x] 06-02-PLAN.md — ConversationRecorder: chunked silence-bounded WAV writer
- [x] 06-03-PLAN.md — ConversationPipeline: multi-model AI analysis, synthesis, file coalescing
- [x] 06-04-PLAN.md — ConversationManager state machine + ConversationStatusWindow
- [x] 06-05-PLAN.md — ConversationViewer: two-panel GTK file browser (Gtk.Paned)
- [x] 06-06-PLAN.md — ConversationDialog + ConversationQAWindow
- [x] 06-07-PLAN.md — App wiring + Settings Phase 6 section
- [x] 06-08-PLAN.md — Pre-verification checks + human verification

### Phase 6.1: Conversation Status Enhancements
**Goal**: ConversationStatusWindow gives real-time feedback on silence and transcription so the user can tell at a glance whether voice input is being detected and what was captured in the last chunk
**Depends on**: Phase 6
**Requirements**: CONV-06, CONV-07
**Success Criteria** (what must be TRUE):
  1. A silence timer is visible in the status window, counting up in whole seconds from when silence begins; it resets to 0 immediately when voice is detected
  2. The most recent chunk's transcript text is displayed in the status window, updating each time a chunk completes transcription
**Plans**: 2 plans

Plans:
- [x] 06.1-01-PLAN.md — Add on_silence_tick callback to ConversationRecorder; add silence + transcript labels to ConversationStatusWindow
- [x] 06.1-02-PLAN.md — Wire silence tick and transcript forwarding in ConversationManager; human verification

### Phase 7: Hotkey Customization
**Goal**: User can configure all hotkeys (recording start/stop, replay, conversation mode) through Settings with support for key combinations
**Depends on**: Phase 6
**Requirements**: HOTKEY-01, HOTKEY-02
**Success Criteria** (what must be TRUE):
  1. Settings includes a hotkey picker for each action (record, stop, conversation mode, replay failed)
  2. User can set key combinations (e.g. Fn+C, Fn+R) and changes take effect without restart
**Plans**: 4 plans

Plans:
- [ ] 07-01-PLAN.md — Config defaults + HotkeyManager backend refactor (parse_combo, combo_display, reload_bindings, apply_binding_override) + history_window fix + app.py wiring
- [ ] 07-02-PLAN.md — Settings UI Hotkeys section (press-to-capture, conflict detection, per-hotkey reset, Reset All, Save)
- [ ] 07-03-PLAN.md — Tests: config defaults/backfill, combo helpers, conflict detection, HotkeyManager reload, capture state machine, history_window regression
- [ ] 07-04-PLAN.md — Code review of all 5 modified files

### Phase 8: Slack Integration
**Goal**: User can connect Slack workspaces via guided token setup in Settings and linux-speech-flow records Slack huddle sessions (mic + system audio) with activation word commands, posting results to Slack as Block Kit + transcript attachment
**Depends on**: Phase 6
**Requirements**: SLACK-01, SLACK-02, SLACK-03, SLACK-04, SLACK-05
**Success Criteria** (what must be TRUE):
  1. User can configure a Slack workspace/channel in Settings and transcription output is posted there
  2. linux-speech-flow can join a Slack huddle as a bot participant and record the session
  3. In huddle mode, silence is used to create chunk boundaries but silence audio is not recorded — chunks contain voice-only audio
  4. In huddle mode, the silence timer in ConversationStatusWindow is hidden (not meaningful in a call context)
  5. When the Slack huddle ends, linux-speech-flow automatically stops the session and triggers the full transcription and analysis pipeline
**Plans**: 6 plans

Plans:
- [ ] 08-01-PLAN.md — Foundation: slack-sdk+numpy deps, config defaults, SlackManager, huddle hotkey, Settings Integrations section
- [ ] 08-02-PLAN.md — HuddleRecorder (null-sink dual-source) + HuddleStatusWindow (dedicated GTK, no silence timer)
- [ ] 08-03-PLAN.md — SlackSocket (SocketModeClient daemon thread) + HuddleManager (orchestration, activation word, confidence alerting)
- [ ] 08-04-PLAN.md — App wiring (HotkeyManager, tray item) + post_huddle_results (Block Kit + .md upload)
- [ ] 08-05-PLAN.md — Test audit and full regression run
- [ ] 08-06-PLAN.md — Human verification of all 5 SLACK requirements

### Phase 8.1: Help Dialog
**Goal**: User can access a comprehensive in-app help window from the tray that explains every feature, hotkey, and workflow in plain language
**Depends on**: Phase 8
**Requirements**: HELP-01, HELP-02
**Success Criteria** (what must be TRUE):
  1. Tray "Help" menu item opens a detailed help window with sections for each feature (transcription, conversation mode, settings, hotkeys)
  2. Each section explains what the feature does, how to use it, and any prerequisites (e.g. API key required)
**Plans**: TBD

Plans:
- [ ] 8.1-01: TBD

### Phase 9: Packaging & Distribution
**Goal**: User can install linux-speech-flow as a .deb package or via pip and have it launch automatically at login
**Depends on**: Phase 1, Phase 2, Phase 3, Phase 4, Phase 5
**Requirements**: DIST-01, DIST-02, DIST-03, DIST-04, DIST-05
**Success Criteria** (what must be TRUE):
  1. User can install via `apt install ./linux-speech-flow_*.deb` on Ubuntu 22.04+, Debian 12+, Pop!_OS 22.04+
  2. .deb bundles a Python virtualenv so it works without pip or system Python modifications
  3. After install, linux-speech-flow launches automatically at login via XDG autostart .desktop entry
  4. User can alternatively install via `pip install linux-speech-flow` from PyPI
  5. README clearly documents required system dependencies (xdotool, xclip, libnotify-bin, gnome-shell-extension-appindicator)
**Plans**: TBD

Plans:
- [ ] 09-01: TBD
- [ ] 09-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 6.1 -> 7 -> 8 -> 8.1 -> 9
Note: Phases 4 and 5 both depend on Phase 3 and could execute in parallel.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Configuration | 5/5 | Complete | 2026-02-19 |
| 2. Audio Capture & Hotkey | 5/5 | Complete | 2026-02-19 |
| 3. Transcription & Text Injection | 6/6 | Complete | 2026-02-21 |
| 4. System Tray & Desktop Integration | 3/3 | Complete | 2026-02-21 |
| 4.1. FreeFlow Rename and Codebase Cleanup | 3/3 | Complete | 2026-02-21 |
| 5. Pipeline History | 4/4 | Complete | 2026-02-21 |
| 6. Conversation Mode | 8/8 | Complete | 2026-02-21 |
| 6.1. Conversation Status Enhancements | 2/2 | Complete   | 2026-03-03 |
| 7. Hotkey Customization | 4/4 | Complete   | 2026-03-04 |
| 8. Slack Integration | 5/6 | In Progress|  |
| 8.1. Help Dialog | 0/? | Not started | - |
| 9. Packaging & Distribution | 0/? | Not started | - |
