# Phase 8: Slack Integration - Research

**Researched:** 2026-03-03
**Domain:** Slack Python SDK, PulseAudio dual-source capture, OAuth2 desktop flows, Socket Mode WebSockets
**Confidence:** MEDIUM (Slack API patterns HIGH; OAuth localhost constraint is a CRITICAL BLOCKER requiring design decision; PulseAudio dual-capture MEDIUM)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Slack integration is huddle recordings ONLY — push-to-talk and conversation mode stay local
- Pre-registered Slack app (client_id + client_secret bundled) with OAuth2 authorization code flow: system browser (xdg-open) + localhost callback
- Multiple workspaces supported; each with own channel configuration and bot display name (default: "Linux Speech Flow")
- New "Integrations" section in SettingsWindow (below "AI Integrations")
- Manual trigger: Ctrl+Alt+H hotkey (6th configurable hotkey, extends Phase 7 HotkeyManager)
- Auto-detect: Slack Socket Mode WebSocket listens for huddle events; modes: Manual hotkey only / Auto-detect with prompt / Auto-detect always
- Tray menu: "Start/Stop Huddle Recording" item
- Audio capture: system audio (PulseAudio monitor sink) + microphone simultaneously, mixed into one stream for Whisper
- Same chunked silence-detection architecture as ConversationRecorder; silence timer hidden in HuddleStatusWindow
- Default activation word: "conyo" (configurable); detected post-transcription; activation chunk NOT added to transcript
- 11 voice commands: start/stop recording, pause/resume, summarize, calibrate, status, list action items, note [text], topic [title], help
- Bot posts welcome message with full command list on recording start
- Dedicated HuddleStatusWindow (NOT ConversationStatusWindow reused)
- Post-huddle: same ConversationPipeline (AI analysis + Q&A dialog); always shows post-stop dialog
- Results saved to ~/Documents/conversations/ AND posted to Slack channel/DM where huddle occurred
- Slack message format: Block Kit (rich) + .md file attachment for raw transcript
- Token stored in ~/.config/linux-speech-flow/config.json (existing 600-permissions pattern)
- Recording stops when Jon leaves huddle (system audio stops); headless bot mode deferred
- Confidence alerting: below-threshold triggers Slack channel post + local desktop notification

### Claude's Discretion
- Exact Slack API scopes required (researcher to determine)
- PulseAudio mixed-source implementation (null sink loopback vs Python audio mixing)
- OAuth callback local server implementation (port selection, error handling) — **CRITICAL: see blocker below**
- `conyo calibrate` audio threshold auto-adjustment beyond the Slack message
- Slack Block Kit exact layout and styling
- HuddleStatusWindow sizing and GTK layout details
- Speaker attribution (if Whisper diarization available; otherwise single-stream transcript)

### Deferred Ideas (OUT OF SCOPE)
- MCP bridge commands ("conyo send email to Chris", "conyo create tasks in Jira")
- Headless bot mode (bot continues recording after Jon leaves)
- Conversation mode posting to Slack (regular conversation mode stays local)
- Speaker diarization (attributing transcript segments to speakers by name)
- Push-to-talk posting to Slack
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SLACK-01 | User can connect one or more Slack workspaces via OAuth2 browser flow (pre-registered app); credentials stored in config.json | OAuth2 flow with slack_sdk.oauth; HTTPS redirect URI is a CRITICAL BLOCKER — see OAuth section |
| SLACK-02 | When a Slack huddle is detected (auto or manual Ctrl+Alt+H), linux-speech-flow records the session by capturing system audio + microphone simultaneously via PulseAudio | PulseAudio null-sink + loopback pattern; two pasimple streams + numpy mixing OR single combined monitor source |
| SLACK-03 | Huddle recording uses voice-only chunks (silence detection for chunk boundaries; silence audio not recorded); silence timer hidden in HuddleStatusWindow | ConversationRecorder architecture reused; HuddleRecorder extends with dual-source |
| SLACK-04 | Voice activation word (default "conyo", configurable) triggers in-call commands; bot posts welcome message + command list to Slack on recording start | Post-transcription string scanning; slack_sdk WebClient.chat_postMessage with Block Kit |
| SLACK-05 | When huddle ends, full conversation pipeline runs (AI analysis + Q&A dialog); results posted to Slack as Block Kit message + .md file attachment and saved locally | ConversationPipeline reuse; slack_sdk files_upload_v2 + chat_postMessage blocks |
</phase_requirements>

---

## Summary

Phase 8 implements Slack huddle recording integration, connecting linux-speech-flow to Slack workspaces so huddles are automatically captured, transcribed, AI-analyzed, and posted to Slack. The phase extends the existing ConversationRecorder architecture with dual-source PulseAudio capture (system monitor + microphone), adds Socket Mode WebSocket event listening for huddle detection, and adds a new HuddleManager class coordinating the entire flow.

**CRITICAL BLOCKER DISCOVERED:** Slack requires HTTPS for all OAuth redirect URIs and does NOT allow `http://localhost` loopback redirects. This is explicitly documented and enforced. The planned "localhost HTTP callback" approach in CONTEXT.md will fail at Slack app registration. Options are: (1) use Python `ssl` + a self-signed cert on localhost with `https://127.0.0.1:PORT` registered in the app manifest, (2) use a stable HTTPS redirect relay URL pre-configured in the app manifest that captures the code and redirects to localhost via HTTP internally (the code itself is not secret, only the client_secret is), or (3) use the Slack Socket Mode App-Level Token flow instead of a full OAuth bot install. This must be resolved before implementation begins.

**Primary recommendation:** Use `slack-sdk>=3.40.1` (not `slack-bolt`) for lightweight integration. Use PulseAudio null-sink + two pasimple streams with numpy mixing for dual-source capture. Resolve the HTTPS OAuth redirect constraint via a pre-configured HTTPS relay endpoint bundled with the app's registered redirect URLs.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slack-sdk | >=3.40.1 | Slack API: WebClient, SocketModeClient, OAuth | Official Slack Python SDK; slack-bolt adds unnecessary framework overhead for this use case |
| pulsectl | >=24.12.0 | PulseAudio introspection (sink/source enumeration, module load via subprocess) | Already used in project for device enumeration; pactl command wrapping for null-sink creation |
| numpy | latest | Mix two audio streams (int16 addition with int32 overflow protection) | Required for dual-source mixing; already transitive dep via groq/httpx |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| websocket-client | >=1.6.0 | WebSocket transport for SocketModeClient | slack-sdk's default SocketModeClient transport; already pulls in via slack-sdk |
| ssl (stdlib) | stdlib | HTTPS server for OAuth callback | Needed IF self-signed cert approach chosen for OAuth redirect |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| slack-sdk SocketModeClient | slack-bolt SocketModeHandler | Bolt adds ~10 extra deps and framework overhead; raw SDK gives direct thread control needed for GTK integration |
| numpy int16 mixing | PulseAudio combine-sink (single stream) | combine-sink is cleaner but requires pactl module-combine-sink setup and Slack audio output routing; two pasimple streams is more controllable |
| pasimple dual-stream + numpy | GStreamer pipeline | GStreamer handles mixing natively but introduces heavy dependency; pasimple is already project-standard |

**Installation:**
```bash
pip install "slack-sdk>=3.40.1" "pulsectl>=24.12.0" numpy
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/linux_speech_flow/
├── slack_manager.py          # OAuth token management, workspace list, WebClient API calls
├── slack_socket.py           # SocketModeClient wrapper: huddle event detection, auto-reconnect
├── huddle_recorder.py        # Dual-source PulseAudio capture (extends ConversationRecorder pattern)
├── huddle_manager.py         # Orchestrates HuddleRecorder + activation word + HuddleStatusWindow
├── huddle_status.py          # HuddleStatusWindow GTK class (new, NOT ConversationStatusWindow)
└── [existing files modified]
    ├── hotkey.py             # Add 'huddle' to HOTKEY_DEFAULTS/CONFIG_KEYS/ACTION_LABELS
    ├── config.py             # Add DEFAULT_CONFIG Slack keys
    ├── settings.py           # Add "Integrations" section
    ├── tray.py               # Add "Start/Stop Huddle Recording" menu item
    └── app.py                # Wire HuddleManager, SlackManager into do_startup()
```

### Pattern 1: SlackManager — Token + API Layer
**What:** Manages workspace tokens, bot names, WebClient calls (post message, upload file)
**When to use:** Anywhere Slack API is called (posting results, mid-call commands)

```python
# Source: slack-sdk 3.40.1 official docs
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackManager:
    def __init__(self):
        self._workspaces: dict[str, dict] = {}  # team_id -> {token, bot_name, channel_id}

    def post_message(self, team_id: str, channel_id: str, text: str, blocks: list = None) -> bool:
        token = self._workspaces[team_id]["token"]
        client = WebClient(token=token)
        try:
            client.chat_postMessage(
                channel=channel_id,
                text=text,       # fallback for notifications
                blocks=blocks,   # Block Kit rich message
            )
            return True
        except SlackApiError as exc:
            logger.error("Slack post failed: %s", exc.response["error"])
            return False

    def upload_file(self, team_id: str, channel_id: str, file_path: str, title: str) -> bool:
        token = self._workspaces[team_id]["token"]
        client = WebClient(token=token)
        try:
            client.files_upload_v2(
                channel=channel_id,
                file=file_path,
                title=title,
            )
            return True
        except SlackApiError as exc:
            logger.error("Slack upload failed: %s", exc.response["error"])
            return False
```

### Pattern 2: SocketModeClient in Daemon Thread (GTK-safe)
**What:** Slack Socket Mode WebSocket in a daemon thread; events dispatched to GTK main thread via GLib.idle_add
**When to use:** Huddle auto-detection

```python
# Source: slack-sdk docs + PyGObject threading guide
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.web import WebClient
import threading
from gi.repository import GLib

class SlackSocket:
    def start(self, app_token: str, bot_token: str, on_huddle_event):
        self._client = SocketModeClient(
            app_token=app_token,   # xapp-prefixed app-level token
            web_client=WebClient(token=bot_token),
        )
        self._client.socket_mode_request_listeners.append(
            self._make_listener(on_huddle_event)
        )
        # Non-blocking connect; GTK main loop stays on main thread
        threading.Thread(
            target=self._client.connect,
            daemon=True,
        ).start()

    def _make_listener(self, on_huddle_event):
        def listener(client, req):
            if req.type == "events_api":
                payload = req.payload
                event = payload.get("event", {})
                if event.get("type") == "user_huddle_changed":
                    # Dispatch to GTK main thread
                    GLib.idle_add(on_huddle_event, event)
            client.send_socket_mode_response(
                SocketModeResponse(envelope_id=req.envelope_id)
            )
        return listener
```

### Pattern 3: HuddleRecorder — Dual-Source PulseAudio Capture
**What:** Two pasimple streams (microphone + system monitor) read in lockstep threads; numpy mixing; single chunk output
**When to use:** Huddle mode audio capture

The RECOMMENDED approach is to use a PulseAudio null-sink as a combined mixer rather than numpy mixing in Python. This is more reliable and avoids clock-drift issues between two independent pasimple streams.

**Null-sink setup (via subprocess + pactl):**
```python
import subprocess
import pulsectl

class HuddleRecorder:
    """Dual-source recorder: mic + system audio via PulseAudio null-sink mix."""

    def _setup_mix_sink(self, mic_device: str, system_monitor: str) -> str:
        """Create null sink + loopback for mic+monitor mix. Returns mix_monitor source name."""
        # Create a null sink named 'lsf-huddle-mix'
        result = subprocess.run(
            ['pactl', 'load-module', 'module-null-sink',
             'sink_name=lsf-huddle-mix',
             'sink_properties=device.description=LSF_Huddle_Mix'],
            capture_output=True, text=True, check=True,
        )
        self._null_sink_module = result.stdout.strip()

        # Loopback microphone into mix sink
        result2 = subprocess.run(
            ['pactl', 'load-module', 'module-loopback',
             f'source={mic_device}', 'sink=lsf-huddle-mix', 'latency_msec=1'],
            capture_output=True, text=True, check=True,
        )
        self._mic_loopback_module = result2.stdout.strip()

        # Loopback system monitor into mix sink
        result3 = subprocess.run(
            ['pactl', 'load-module', 'module-loopback',
             f'source={system_monitor}', 'sink=lsf-huddle-mix', 'latency_msec=1'],
            capture_output=True, text=True, check=True,
        )
        self._sys_loopback_module = result3.stdout.strip()

        return 'lsf-huddle-mix.monitor'

    def _teardown_mix_sink(self):
        for mod_id in [self._sys_loopback_module, self._mic_loopback_module, self._null_sink_module]:
            if mod_id:
                subprocess.run(['pactl', 'unload-module', mod_id], capture_output=True)
```

After setup, `lsf-huddle-mix.monitor` is the single source name passed to `pasimple.PaSimple` as `device_name`. The existing `ConversationRecorder._record_loop()` logic works unchanged — only the `device_name` changes. This is cleaner than Python-level mixing.

**System monitor source name lookup:**
```python
import pulsectl

def get_default_monitor_source() -> str:
    """Return the monitor source name for the default output sink."""
    with pulsectl.Pulse('lsf-monitor-lookup') as pulse:
        server_info = pulse.server_info()
        default_sink_name = server_info.default_sink_name
        return f"{default_sink_name}.monitor"
```

### Pattern 4: Activation Word Detection
**What:** Post-transcription scan of each chunk text for "conyo [command]"
**When to use:** Every chunk in HuddleManager._on_chunk_transcribed

```python
import re

ACTIVATION_WORD = "conyo"  # configurable from config

COMMANDS = {
    "start recording": "_cmd_start_recording",
    "stop recording": "_cmd_stop_recording",
    "pause": "_cmd_pause",
    "resume": "_cmd_resume",
    "summarize": "_cmd_summarize",
    "calibrate": "_cmd_calibrate",
    "status": "_cmd_status",
    "list action items": "_cmd_list_action_items",
    "help": "_cmd_help",
}
# note [text] and topic [title] use prefix matching

def detect_activation(text: str, word: str) -> tuple[str | None, str | None]:
    """Returns (command_key, remainder) or (None, None) if no match."""
    pattern = re.compile(
        rf'\b{re.escape(word)}\s+(.+)', re.IGNORECASE
    )
    m = pattern.search(text.lower())
    if not m:
        return None, None
    remainder = m.group(1).strip()
    # Check fixed commands first
    for cmd in sorted(COMMANDS, key=len, reverse=True):
        if remainder.startswith(cmd):
            return cmd, remainder[len(cmd):].strip()
    # Prefix commands
    if remainder.startswith("note "):
        return "note", remainder[5:].strip()
    if remainder.startswith("topic "):
        return "topic", remainder[6:].strip()
    return None, None
```

### Pattern 5: Block Kit Message Construction
**What:** Rich Slack message with section blocks, dividers, bold headers
**When to use:** Post-huddle results posting, mid-call `conyo summarize`

```python
# Source: slack-sdk official docs + Block Kit reference
def build_huddle_result_blocks(header: str, summary: str, analysis: str) -> list[dict]:
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Executive Summary*\n{summary}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*AI Analysis*\n{analysis}"},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "_Full transcript attached as .md file_"},
            ],
        },
    ]
```

### Pattern 6: HotkeyManager Extension (6th Hotkey)
**What:** Add 'huddle' to the three existing dicts; same pattern as existing 5 hotkeys
**When to use:** hotkey.py modification

```python
# Following exact existing pattern in hotkey.py:
HOTKEY_DEFAULTS = {
    'record':       'ctrl+alt+r',
    'stop':         'ctrl+alt+r',
    'conversation': 'ctrl+alt+c',
    'reprocess':    'ctrl+alt+p',
    'feedback':     'ctrl+alt+f',
    'huddle':       'ctrl+alt+h',   # ADD THIS
}

HOTKEY_CONFIG_KEYS = {
    # ... existing ...
    'huddle': 'hotkey_huddle',      # ADD THIS
}

HOTKEY_ACTION_LABELS = {
    # ... existing ...
    'huddle': 'Huddle Recording',   # ADD THIS
}
```

And add to `_on_press` dispatch in HotkeyManager:
```python
elif self._matches_binding(key, 'huddle'):
    if self._state == self._STATE_IDLE:
        GLib.idle_add(self._huddle_start)
    elif self._state == self._STATE_HUDDLE:
        GLib.idle_add(self._huddle_stop)
```
This requires adding `_STATE_HUDDLE = "huddle"` and `on_huddle_start`/`on_huddle_stop` callbacks.

### Anti-Patterns to Avoid
- **Running `handler.start()` (blocking) on the GTK main thread:** Always use `handler.connect()` in a daemon thread; `start()` blocks the calling thread
- **Using `files.upload` (deprecated):** Use `files_upload_v2` only; `files.upload` was sunset for new apps May 2024, full sunset November 2025
- **Passing channel name strings to `files_upload_v2`:** Must use channel ID (C-prefix), not `#channel-name`
- **Two independent pasimple streams for mixing:** Clock drift between streams causes sync issues over long huddles; use the null-sink + loopback approach instead
- **Calling GTK/GLib directly from Slack event listener threads:** All GTK operations from Bolt/SDK listener threads must go through `GLib.idle_add()`

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket connection + reconnect | Custom WebSocket client | `slack_sdk.socket_mode.SocketModeClient` | Handles reconnect, ping/pong, envelope ACKs |
| File upload to Slack | Custom multipart HTTP | `WebClient.files_upload_v2()` | Three-step API (getUploadURL, upload, complete) wrapped in one call |
| Block Kit JSON construction | Raw dict assembly | `slack_sdk.models.blocks` or plain dict pattern | Block Kit schema validation; `chat.postMessage` rejects invalid blocks |
| Audio stream mixing | Custom numpy mixing loop | PulseAudio null-sink + loopback | Handles clock drift, sample rate differences; null-sink runs in PulseAudio daemon |
| Silence detection for chunks | Re-implementing RMS logic | Extend `ConversationRecorder` architecture | All silence detection, calibration, chunk lifecycle already implemented and tested |

**Key insight:** The null-sink approach offloads audio mixing entirely to PulseAudio — the Python code only reads from a single monitor source, identical to existing ConversationRecorder behavior.

---

## Common Pitfalls

### Pitfall 1: Slack OAuth HTTPS Redirect URI Requirement — CRITICAL BLOCKER
**What goes wrong:** Slack rejects `http://localhost:PORT` redirect URIs at app registration and at runtime. This is enforced by Slack's app configuration, not worked around in code.
**Why it happens:** Slack enforces HTTPS for all redirect URIs per their security policy. Unlike Google/Microsoft, Slack does NOT make a loopback exception per RFC 8252.
**How to avoid:** Choose ONE strategy during app manifest registration:
  - **Option A (Recommended):** Register `https://127.0.0.1:PORT` with a self-signed cert in the Python HTTPS server. Slack allows `127.0.0.1` with HTTPS. Python's `ssl.SSLContext` can wrap `http.server`. Browser shows a security warning that the user must accept once.
  - **Option B:** Pre-register a stable HTTPS URL (e.g., a Cloudflare Worker or Vercel edge function) that 302-redirects to `http://localhost:PORT/callback?code=...`. The authorization code is not secret — only the client_secret is (never sent to the relay). This is used by some desktop apps (VS Code, etc.).
  - **Option C:** If the Slack app is only for personal/workspace use (not distributed), use an App-Level Token with Socket Mode only and skip OAuth entirely — configure bot token manually in Settings.
**Warning signs:** `invalid_redirect_uri` error when clicking "Allow" in Slack auth page.

### Pitfall 2: `files_upload_v2` Requires Channel ID Not Name
**What goes wrong:** Passing `channel="#general"` or `channel="general"` returns `invalid_channel`.
**Why it happens:** `files_upload_v2` requires the channel ID (starts with `C`, `G`, `D` for public/private/DM).
**How to avoid:** Store channel ID, not channel name, after OAuth. Use `conversations.list` to let user select a channel and store its `id` field.
**Warning signs:** `SlackApiError: invalid_channel` on file upload.

### Pitfall 3: `user_huddle_changed` Fires for ALL Workspace Users
**What goes wrong:** Bot receives huddle events for every user in the workspace, not just the bot owner.
**Why it happens:** `user_huddle_changed` is a workspace-level event broadcast to all connections with `users:read`.
**How to avoid:** Filter by `event["user"]["id"]` matching the bot installer's user ID (available from `oauth.v2.access` response as `authed_user.id`). Store this ID at OAuth time.
**Warning signs:** Spurious huddle-start triggers for coworker huddles.

### Pitfall 4: PulseAudio Module Orphaning on Crash
**What goes wrong:** If the app crashes during a huddle, the `module-null-sink` and `module-loopback` modules remain loaded in PulseAudio, consuming resources and causing naming conflicts on restart.
**Why it happens:** `pactl unload-module` is only called in the teardown path.
**How to avoid:** At `HuddleRecorder.start()`, first check if `lsf-huddle-mix` sink already exists (via `pulsectl.Pulse.sink_list()`) and unload it if so. Use a `try/finally` block around the recording loop to guarantee teardown.
**Warning signs:** `pactl load-module module-null-sink sink_name=lsf-huddle-mix` fails with "already exists" error.

### Pitfall 5: SocketModeClient `start()` vs `connect()`
**What goes wrong:** Calling `self._client.start()` on any thread blocks that thread indefinitely.
**Why it happens:** `start()` establishes connection AND blocks the calling thread. `connect()` only establishes the connection.
**How to avoid:** Always call `self._client.connect()` from a daemon thread. Leave the GTK main loop running on the main thread.
**Warning signs:** App freezes after Slack connection is initiated.

### Pitfall 6: Whisper Confidence via `verbose_json` Response Format
**What goes wrong:** Existing `transcribe_chunk()` uses default response format (returns `.text` only), so confidence data is unavailable.
**Why it happens:** Groq Whisper only returns segment-level confidence (`avg_logprob`, `no_speech_prob`) when `response_format="verbose_json"`.
**How to avoid:** In `HuddleManager`, call transcription with `response_format="verbose_json"` and extract per-segment `avg_logprob`. Convert to a 0–1 confidence score (avg_logprob of 0.0 = 100%, -1.0 = ~37%). Simple formula: `confidence = max(0.0, min(1.0, 1.0 + avg_logprob))`.
**Warning signs:** Confidence is always `None` or 1.0 (no data returned without verbose_json).

### Pitfall 7: PulseAudio Monitor Source Naming
**What goes wrong:** Using device name `"alsa_output.pci-0000_00_1f.3.analog-stereo.monitor"` hardcoded; this breaks on different hardware.
**Why it happens:** PulseAudio sink names are hardware-dependent.
**How to avoid:** Use `pulsectl.Pulse.server_info().default_sink_name + ".monitor"` for system monitor. Let user select microphone from existing settings. Never hardcode sink names.
**Warning signs:** `pasimple.PaSimpleError: No such entity` on stream open.

---

## Code Examples

Verified patterns from official sources:

### OAuth v2 Token Exchange
```python
# Source: https://docs.slack.dev/authentication/installing-with-oauth
from slack_sdk import WebClient

client = WebClient()  # no token needed for OAuth methods
response = client.oauth_v2_access(
    client_id="your_client_id",
    client_secret="your_client_secret",
    code=authorization_code,
    redirect_uri="https://127.0.0.1:8765/callback",  # must match registered URI
)
bot_token = response["access_token"]          # xoxb-...
authed_user_id = response["authed_user"]["id"]  # user who authorized
team_id = response["team"]["id"]
team_name = response["team"]["name"]
```

### files_upload_v2 (Current API — files.upload deprecated May 2024)
```python
# Source: https://docs.slack.dev/tools/python-slack-sdk/tutorial/uploading-files/
# files.upload fully sunset November 2025
client.files_upload_v2(
    channel=channel_id,       # MUST be channel ID (C-prefix), not name
    file="./transcript.md",
    title="Huddle Transcript — Friday March 6 2026",
    initial_comment="See attached for full transcript.",
)
```

### chat_postMessage with Block Kit
```python
# Source: https://docs.slack.dev/tools/python-slack-sdk/web/
client.chat_postMessage(
    channel=channel_id,
    text="Huddle summary posted",  # fallback for notifications
    blocks=[
        {"type": "header", "text": {"type": "plain_text", "text": "Huddle on Friday, March 6 2026 about: Q2 roadmap"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Executive Summary*\n..."}},
    ],
)
```

### Whisper verbose_json for Confidence
```python
# Source: https://console.groq.com/docs/speech-to-text
with open(wav_path, "rb") as f:
    response = groq_client.audio.transcriptions.create(
        file=("chunk.wav", f),
        model="whisper-large-v3-turbo",
        response_format="verbose_json",
    )
text = response.text
# Confidence from avg_logprob (-1.0 = low, 0.0 = high)
segments = response.segments or []
if segments:
    avg_logprob = sum(s.avg_logprob for s in segments) / len(segments)
    confidence = max(0.0, min(1.0, 1.0 + avg_logprob))
else:
    confidence = 1.0  # no segments = silent chunk
```

### PulseAudio Null-Sink + Loopback Setup
```python
# Source: https://gist.github.com/varqox/c1a5d93d4d685ded539598676f550be8
# Source: pulsectl PyPI docs
import subprocess
import pulsectl

def create_huddle_mix_sink(mic_source: str, system_monitor: str) -> tuple[str, list[str]]:
    """Returns (monitor_source_name, [module_ids_to_unload])."""
    module_ids = []

    # 1. Create null sink
    r = subprocess.run(
        ['pactl', 'load-module', 'module-null-sink',
         'sink_name=lsf-huddle-mix',
         'sink_properties=device.description=LSF_Huddle_Mix'],
        capture_output=True, text=True, check=True,
    )
    module_ids.append(r.stdout.strip())

    # 2. Loopback mic into mix sink
    r = subprocess.run(
        ['pactl', 'load-module', 'module-loopback',
         f'source={mic_source}', 'sink=lsf-huddle-mix', 'latency_msec=1'],
        capture_output=True, text=True, check=True,
    )
    module_ids.append(r.stdout.strip())

    # 3. Loopback system monitor into mix sink
    r = subprocess.run(
        ['pactl', 'load-module', 'module-loopback',
         f'source={system_monitor}', 'sink=lsf-huddle-mix', 'latency_msec=1'],
        capture_output=True, text=True, check=True,
    )
    module_ids.append(r.stdout.strip())

    return 'lsf-huddle-mix.monitor', module_ids


def teardown_huddle_mix_sink(module_ids: list[str]) -> None:
    for mod_id in reversed(module_ids):
        subprocess.run(['pactl', 'unload-module', mod_id], capture_output=True)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `files.upload` | `files_upload_v2` (SDK) | May 2024 (sunset Nov 2025) | Must use new API; old method blocked for new apps |
| Separate mic/monitor pasimple streams + numpy mix | PulseAudio null-sink + loopback | Best practice | Avoids clock drift over long huddles |
| `slack-bolt` SocketModeHandler.start() | `slack-sdk` SocketModeClient.connect() in daemon thread | Ongoing | Lighter dep tree; direct GTK integration |
| HTTP localhost OAuth redirect | HTTPS required | Ongoing Slack policy | Requires HTTPS on callback server |

**Deprecated/outdated:**
- `files.upload`: blocked for new apps since May 2024; sunset November 12, 2025 — use `files_upload_v2`
- `conversations:read` scope: deprecated, replaced by `channels:read`, `groups:read`, `im:read`, `mpim:read` as granular scopes
- RTM (Real-Time Messaging) API: deprecated in favor of Socket Mode
- Classic Slack apps: cannot create new ones since June 2024

---

## Required Slack OAuth Scopes

| Scope | Purpose |
|-------|---------|
| `chat:write` | Post messages to channels |
| `files:write` | Upload files (transcript .md attachment) |
| `channels:read` | List and look up public channels |
| `groups:read` | List and look up private channels |
| `im:read` | List and look up DMs |
| `users:read` | Subscribe to `user_huddle_changed` events |
| `connections:write` | App-level token scope for Socket Mode (separate token, not bot token) |

**Two token types required:**
1. **Bot token** (`xoxb-...`): obtained via OAuth2 `oauth.v2.access`; used for WebClient API calls
2. **App-level token** (`xapp-...`): generated in app settings (not OAuth); used for SocketModeClient

**Stored in config.json per workspace:**
```json
{
  "slack_workspaces": {
    "T1234ABCD": {
      "bot_token": "xoxb-...",
      "app_token": "xapp-...",
      "bot_name": "Linux Speech Flow",
      "channel_id": "C5678EFGH",
      "authed_user_id": "U9012IJKL",
      "team_name": "My Workspace"
    }
  }
}
```

---

## Open Questions

1. **CRITICAL: OAuth HTTPS Redirect URI Strategy**
   - What we know: Slack requires HTTPS for all redirect URIs; `http://localhost` is explicitly blocked
   - What's unclear: Which of the three options (self-signed HTTPS, relay URL, manual token entry) should be implemented for v1
   - Recommendation: For a personal/developer tool like linux-speech-flow, the simplest v1 is to require manual bot token entry in Settings (user creates Slack app, copies bot token). Full OAuth browser flow is a future enhancement. This avoids the HTTPS constraint entirely for v1.

2. **App-Level Token (xapp-) Distribution**
   - What we know: App-level tokens are generated per-app-installation in Slack's app settings (not OAuth); they are not user-specific
   - What's unclear: How to distribute the `xapp-` token alongside `client_id/client_secret` for multi-workspace use
   - Recommendation: If doing manual token entry (v1), user creates their own Slack app and generates both tokens. If doing OAuth flow (later), pre-generate a single `xapp-` token for the pre-registered app.

3. **huddle_state_call_id to Channel Mapping**
   - What we know: `user_huddle_changed` event includes `huddle_state_call_id` but NOT the channel ID directly
   - What's unclear: Is there a Slack API to resolve `huddle_state_call_id` to a channel ID? The Recall.ai approach (bot joins as participant) doesn't apply here.
   - Recommendation: Research `calls.info` API method; alternatively prompt user to configure a default channel per workspace in Settings as v1 fallback.

4. **HuddleRecorder vs ConversationRecorder Inheritance**
   - What we know: ConversationRecorder uses a single pasimple stream; HuddleRecorder needs to set up null-sink first then record from its monitor
   - What's unclear: Whether to subclass ConversationRecorder or create HuddleRecorder as a standalone class that delegates recording to a ConversationRecorder instance after null-sink setup
   - Recommendation: Standalone HuddleRecorder that creates ConversationRecorder(device_name="lsf-huddle-mix.monitor") internally — composition over inheritance, avoids fragile subclass coupling.

---

## Sources

### Primary (HIGH confidence)
- slack-sdk PyPI page — version 3.40.1, module list
- [Slack Socket Mode docs](https://docs.slack.dev/tools/python-slack-sdk/socket-mode/) — SocketModeClient setup, app_token vs bot_token
- [Slack files_upload_v2 tutorial](https://docs.slack.dev/tools/python-slack-sdk/tutorial/uploading-files/) — exact API, scopes, channel ID requirement
- [Slack user_huddle_changed event](https://docs.slack.dev/reference/events/user_huddle_changed/) — payload fields, `users:read` scope, huddle_state field names
- [Slack OAuth installing docs](https://docs.slack.dev/authentication/installing-with-oauth) — token types, oauth_v2_access response
- [Groq Speech-to-Text docs](https://console.groq.com/docs/speech-to-text) — verbose_json, avg_logprob, no_speech_prob
- Existing project source: `conversation_recorder.py`, `conversation_manager.py`, `hotkey.py`, `config.py`

### Secondary (MEDIUM confidence)
- [PulseAudio null-sink + loopback gist](https://gist.github.com/varqox/c1a5d93d4d685ded539598676f550be8) — verified against PulseAudio module docs
- [pulsectl PyPI 24.12.0](https://pypi.org/project/pulsectl/) — server_info().default_sink_name pattern
- [PyGObject threading guide](https://pygobject.readthedocs.io/en/latest/guide/threading.html) — GLib.idle_add + daemon thread pattern (consistent with existing project patterns)
- [Slack scope reference](https://docs.slack.dev/reference/scopes/) — chat:write, files:write, channels:read, groups:read, users:read, connections:write

### Tertiary (LOW confidence — flag for validation)
- Slack HTTPS localhost redirect enforcement: confirmed by multiple community sources but no single definitive official doc with explicit wording on `127.0.0.1` with HTTPS. Recommend testing this during implementation.
- `huddle_state_call_id` to channel mapping: no official Slack API found for this resolution. Marked as Open Question #3.

---

## Metadata

**Confidence breakdown:**
- Standard stack (slack-sdk, pulsectl, numpy): HIGH — verified with official docs and PyPI
- Slack API scopes: HIGH — verified against official scope reference
- OAuth HTTPS constraint: HIGH — confirmed by multiple sources; CRITICAL BLOCKER
- PulseAudio null-sink pattern: MEDIUM — well-documented pattern, needs testing on project's PipeWire/PulseAudio environment
- Huddle event payload / channel resolution: MEDIUM — payload structure confirmed; call_id→channel mapping is LOW

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (Slack API is relatively stable; PulseAudio patterns are stable)
