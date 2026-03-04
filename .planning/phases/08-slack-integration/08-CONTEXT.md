# Phase 8: Slack Integration - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Slack huddle recording bot. When Jon is in a Slack huddle, linux-speech-flow captures the full audio (system output + microphone), runs the conversation mode pipeline post-call (AI analysis + Q&A), and posts the results to the Slack channel or DM where the huddle happened. Push-to-talk transcriptions and regular conversation mode recordings stay local — they are NOT posted to Slack. Slack integration is limited to huddles.

</domain>

<decisions>
## Implementation Decisions

### Slack authentication
- Pre-registered Slack app (client_id + client_secret bundled in linux-speech-flow distribution)
- OAuth2 authorization code flow: Jon clicks "Connect to Slack" → system browser opens (xdg-open) → Slack authorization page → Jon clicks Allow → Slack redirects to localhost callback → token captured and stored
- Local HTTP server spun up transiently on a random port to receive the OAuth callback; server shuts down after token is captured
- Token stored in `~/.config/linux-speech-flow/config.json` (existing 600 permissions pattern)
- **Multiple workspaces** supported: Settings shows a list of connected workspaces, each with its own channel configuration
- Bot display name: user-configurable in Settings per workspace (default: "Linux Speech Flow")

### Settings integration
- New **"Integrations"** section in SettingsWindow, below "AI Integrations"
- Section contains: list of connected Slack workspaces, "Connect to Slack" button to add a new workspace, disconnect button per workspace, bot display name field per workspace
- Huddle auto-detect mode selector (per Settings): Manual hotkey only / Auto-detect with prompt / Auto-detect always
- Activation word field (default: "conyo") — single configurable word
- Confidence alert threshold slider (configurable: below what % transcription confidence triggers an alert)
- Activation word commands listed in Settings help text so Jon knows what's available

### Huddle recording trigger
- **Manual**: Ctrl+Alt+H hotkey (6th configurable hotkey — extends Phase 7 HotkeyManager infrastructure)
- **Auto-detect**: Slack Socket Mode WebSocket listens for huddle events; when a huddle is detected in a connected workspace, behavior depends on the auto-detect mode setting:
  - "Auto-detect with prompt": tray notification appears — "Huddle detected in #channel. [Start Recording] button"
  - "Auto-detect always": recording starts immediately
- **Tray menu**: "Start Huddle Recording" item (below "Start Conversation") — toggles to "Stop Huddle Recording" when active
- Recording stops when Jon leaves the Slack huddle (system audio stops when Jon disconnects — v1 constraint). Headless bot mode (continuing after Jon leaves) is deferred.

### Audio capture
- Capture **both** system audio (PulseAudio monitor source — what plays through speakers, i.e. remote participants) AND microphone simultaneously, mixed into one stream for Whisper transcription
- Same chunked silence-detection architecture as ConversationRecorder — voice-only chunks, no silence audio recorded
- Silence timer hidden in Huddle Status window (per Phase 6.1 decision — silence detection is used for chunk boundaries only, not displayed)

### Activation word ("conyo")
- Default activation word: "conyo" (configurable to any single word in Settings)
- Detected post-transcription: Whisper transcribes each chunk; if the transcription contains the activation word followed by a command, the command is extracted and executed; the activation word chunk is NOT added to the main transcript
- **Full command set for Phase 8:**
  - `conyo start recording` / `conyo stop recording` — start or stop huddle recording mid-session
  - `conyo pause` / `conyo resume` — pause recording temporarily (private side conversation, step away)
  - `conyo summarize` — post an intermediate summary of the conversation so far to the Slack channel immediately
  - `conyo calibrate` — bot posts to Slack: "Please speak one at a time and closer to your mic for better transcription"
  - `conyo status` — bot posts current recording status to Slack (duration, chunks, confidence)
  - `conyo list action items` — bot extracts and posts action items from transcript so far to Slack
  - `conyo note [text]` — inserts `[NOTE: text]` as an annotation at that point in the transcript
  - `conyo topic [title]` — marks a new topic section boundary in the transcript with a heading
  - `conyo help` — bot posts the full command list to the Slack channel
- When recording starts, bot posts a **welcome message** to the Slack channel with the full command list so all participants know how to use it
- MCP bridge commands ("conyo send email to...", "conyo create Jira ticket") — **deferred to future phase**

### Confidence alerting
- When per-chunk Whisper confidence falls below the configured threshold (e.g. overlapping speakers, low volume, mumbling), the bot:
  1. Posts an alert to the Slack channel ("Having trouble understanding — please try speaking one at a time")
  2. Sends a local desktop notification to Jon
- Threshold is user-configurable in Settings (Integrations section)

### Huddle Status window
- **Dedicated GTK window** (separate from ConversationStatusWindow — NOT reused)
- Appears automatically when huddle recording starts
- Displays:
  - Huddle duration (elapsed timer)
  - Chunks recorded count
  - Last chunk transcript (most recent transcribed chunk text)
  - Confidence score for most recent chunk (colored indicator: green/yellow/red)
  - Last executed voice command
  - Active command indicator (spinner when bot is processing a command, e.g. generating summary)
  - Recording mode badge: "MIC + SYSTEM"
  - Slack connection status dot (green = connected, red = disconnected/error)
  - Workspace name + channel/DM name
- Silence timer: **hidden** (per Phase 6.1 CONTEXT.md decision — not meaningful in huddle context)

### Post-huddle pipeline
- When huddle ends (Jon leaves, auto-detected end, or `conyo stop recording`): the same post-stop dialog as conversation mode appears — qualifying questions, AI model selection, Q&A loop
- Dialog is always available/accessible during and after the call (not blocked until end)
- After Q&A loop completes:
  - Results **saved locally** to `~/Documents/conversations/` (same path as conversation mode)
  - Results **posted to Slack** (the channel/DM where the huddle took place — determined automatically from Slack event data)
- Posting failure: error notification with Retry option; local file is always saved regardless of Slack post success

### Slack message format
- **New message** (not a thread reply) in the channel/DM where the huddle occurred
- Message header generated by AI: "Huddle on [day, date] about [concise AI-generated topic]"
- Message body uses **Slack Block Kit** (rich formatting): bold section headers, dividers
- Message sections: Executive Summary → AI Analysis → Prompts and Questions Used
- Raw transcript: uploaded as **.md file attachment** (avoids 40k character limit; Slack renders file previews inline)
- `conyo summarize` mid-call posts a labeled intermediate summary: "Mid-call summary as of [time]: [summary text]"

### What does NOT post to Slack
- Push-to-talk (Ctrl+Alt+R) transcriptions: local only
- Regular conversation mode (Ctrl+Alt+C) recordings: local only
- Only huddle recordings post to Slack

### Claude's Discretion
- Exact Slack API scopes required (researcher to determine: `chat:write`, `files:upload`, `channels:read`, `connections:write` for Socket Mode, etc.)
- PulseAudio mixed-source implementation (null sink loopback vs Python audio mixing)
- OAuth callback local server implementation (port selection, error handling)
- `conyo calibrate` audio threshold auto-adjustment (beyond the Slack message, whether any RMS threshold parameters are adjusted automatically)
- Slack Block Kit exact layout and styling within the message
- HuddleStatusWindow sizing and GTK layout details
- Speaker attribution (if Whisper diarization is available, note who spoke; otherwise single-stream transcript)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ConversationRecorder` (conversation_recorder.py): chunked silence-detection audio capture, `on_chunk_ready(wav_path)`, `on_silence_tick` — huddle mode extends this with dual-source (mic + system) audio
- `ConversationManager` (conversation_manager.py): orchestrates recorder + per-chunk transcription, `on_session_complete(transcript, metadata)` — this callback is where Slack posting hooks in
- `HotkeyManager` (hotkey.py): Phase 7 added configurable bindings + `reload_bindings()` — Ctrl+Alt+H is the 6th hotkey, follows same pattern
- `SettingsWindow` (settings.py): "Integrations" section follows existing pattern (Gtk.Label title-4 + label/widget rows)
- `ConversationPipeline` (conversation_pipeline.py): post-stop dialog + AI analysis + Q&A — huddle mode reuses this pipeline
- `config.py` DEFAULT_CONFIG: new Slack keys (workspace tokens, bot name, activation word, auto-detect mode, confidence threshold) backfill automatically via existing `load_config()` merge
- `tray.py`: existing "Start Conversation" tray item pattern — "Start Huddle Recording" follows same pattern

### Established Patterns
- Settings sections: `Gtk.Label` with `add_css_class("title-4")`, rows as `Gtk.Box(HORIZONTAL)` with label left, widget right
- Config backfill: new keys in `DEFAULT_CONFIG` auto-backfilled — no migration code
- GTK threading: operations from background threads must use `GLib.idle_add()`
- `Gtk.Window(modal=True)` — project pattern; no `Gtk.Dialog`
- Token/API keys storage: `~/.config/linux-speech-flow/config.json` at 600 permissions
- Deferred module imports inside methods to avoid circular imports (e.g., `from linux_speech_flow.conversation_status import ConversationStatusWindow` inside method body)

### Integration Points
- `app.py`: `do_startup()` constructs HotkeyManager — Ctrl+Alt+H binding added here
- `HotkeyManager`: 6th configurable hotkey, same `_bindings` dict + `apply_binding_override()` pattern
- `tray.py`: menu item construction — new "Start/Stop Huddle Recording" item added alongside "Start/Stop Conversation"
- `ConversationManager.on_session_complete`: Slack posting logic attaches here, receives full `transcript` + `metadata` dict
- New `SlackManager` class: handles OAuth token management, workspace list, Socket Mode WebSocket, message posting, file upload
- New `HuddleManager` class (or extended ConversationManager): orchestrates PulseAudio dual-source capture, activation word detection, Slack alerting

</code_context>

<specifics>
## Specific Ideas

- Activation word "conyo" (Spanish slang) — Jon's preferred default; phonetically distinct, unlikely to appear in normal conversation
- Welcome message format: "Hi, I'm recording this huddle. Available commands: [conyo start/stop recording | conyo pause/resume | conyo summarize | conyo calibrate | conyo status | conyo list action items | conyo note [text] | conyo topic [title] | conyo help]"
- Huddle post header example: "Huddle on Friday, March 6th 2026 about: product roadmap priorities for Q2"
- Jon: "ending is when the bot is the last participant" — auto-detect end via Slack huddle event (last participant leaves = huddle ends)
- Jon: "we may only want to engage this for planning sessions and not all huddles" — this is why auto-detect with prompt (not auto-always) is the recommended default
- Local file save path: `~/Documents/conversations/` — same as conversation mode (unified location for all session types)
- Per Phase 6.1 CONTEXT.md: "In a future Slack huddle integration, the silence timer should be hidden (not meaningful in a call)" — confirmed and implemented in HuddleStatusWindow

</specifics>

<deferred>
## Deferred Ideas

- **MCP bridge commands** ("conyo send an email to Chris", "conyo create tasks in Jira") — significant new capability requiring separate phase; Jon confirmed this is future work
- **Headless bot mode** (bot continues recording after Jon leaves the Slack huddle) — requires deeper Slack API/RTC research; not feasible with current public Slack API; deferred to future phase
- **Conversation mode posting to Slack** — Jon confirmed regular conversation mode stays local; Slack is huddle-only
- **Speaker diarization** (attributing transcript segments to individual speakers by name) — Whisper large-v3 has limited diarization; full attribution is a future enhancement
- **Push-to-talk posting to Slack** — Jon explicitly said "we should only have the Slack bot interface with huddles"

</deferred>

---

*Phase: 08-slack-integration*
*Context gathered: 2026-03-03*
