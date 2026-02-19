# External Integrations

**Analysis Date:** 2026-02-18

## APIs & External Services

**Groq API:**
- Transcription service via Whisper model
  - SDK/Client: Native URLSession with custom multipart form handling
  - Base URL: `https://api.groq.com/openai/v1`
  - Model: `whisper-large-v3`
  - Auth: Bearer token in Authorization header (`apiKey`)
  - Implementation: `TranscriptionService.swift`
  - Timeout: 20 seconds
  - Validates API key by hitting `/models` endpoint (read-only check)

- Post-processing LLM via chat completions
  - Base URL: `https://api.groq.com/openai/v1/chat/completions`
  - Model: `meta-llama/llama-4-scout-17b-16e-instruct`
  - Auth: Bearer token in Authorization header (`apiKey`)
  - Implementation: `PostProcessingService.swift`
  - Timeout: 20 seconds
  - Used for context-aware transcription cleanup with custom vocabulary support

**GitHub API:**
- Release checking and update downloads
  - Endpoint: `https://api.github.com/repos/zachlatta/freeflow/releases/latest`
  - Accept header: `application/vnd.github+json`
  - No authentication required (public repo)
  - Implementation: `UpdateManager.swift`
  - Parses JSON response to extract DMG asset and publication date
  - Implements stability buffer (3-day wait before recommending new releases)

## Data Storage

**Local File System:**
- Application support directory: `~/Library/Application Support/FreeFlow/`
  - Settings file: `.settings` (JSON format, user-readable)
  - Stores Groq API key, custom vocabulary
  - File permissions: 0600 (owner read/write only)

- Temporary storage for updates:
  - `~/Library/Temporary Items/` for DMG downloads and extraction
  - Automatic cleanup after installation

**Preferences:**
- macOS UserDefaults via `com.zachlatta.freeflow` bundle identifier
  - Stores: setup completion status, hotkey selection, launch-at-login state, last update check date
  - Persisted via standard NSUserDefaults mechanisms

**Pipeline History:**
- CoreData store for transcription history
  - Implementation: `PipelineHistoryStore.swift`
  - Tracks up to 20 most recent transcriptions with timestamps
  - No network persistence (local only)

**Audio Files:**
- Temporary WAV files recorded during dictation
  - Sent to Groq transcription API
  - Stored in system temp directory during processing
  - Automatically deleted after transcription

## Authentication & Identity

**Groq API Key:**
- Single API key per user installation
- Obtained from `https://groq.com/` by user
- Stored in application support directory (not Keychain anymore)
- Set during initial setup via `SetupView.swift`
- Validated before use via `TranscriptionService.validateAPIKey()`

**No Other Auth:**
- GitHub API requests are unauthenticated
- No user login/authentication system
- No cloud synchronization or multi-device support

## Monitoring & Observability

**Error Tracking:**
- None - no external error reporting service

**Logs:**
- Local os.log via `OSLog(subsystem: "com.zachlatta.freeflow", category: "Recording")`
- Used in `AppState.swift` for `recordingLog`
- Accessible via Console.app or `log stream` CLI

**Debugging:**
- Debug overlay panel in app (`PipelineDebugPanelView.swift`, `PipelineDebugContentView.swift`)
- Displays pipeline execution flow, context summaries, post-processing prompts
- Toggled via app state flag `isDebugOverlayActive`

## CI/CD & Deployment

**Hosting:**
- GitHub Releases - distribution of .dmg files
- Repository: `zachlatta/freeflow`

**Update Mechanism:**
- In-app update checker in `UpdateManager.swift`
- Automatically checks GitHub releases API every 7 days (or on user request)
- Downloads .dmg directly from GitHub release assets
- Mounts DMG, extracts .app bundle, replaces current installation
- Relaunches app after update via shell script

**Code Signing:**
- macOS code signing with identity `FreeFlow Dev` (for dev builds)
- Production builds notarized for distribution
- Entitlements in `FreeFlow.entitlements`

## Environment Configuration

**Required env vars:**
- None - API key is stored locally and set via UI setup

**Secrets location:**
- File system: `~/.Library/Application Support/FreeFlow/.settings`
- No .env files or environment-based configuration

**Runtime configuration:**
- Hotkey selection: User-configurable via settings (Fn, Option+Shift, etc.)
- Microphone selection: User-configurable, auto-detects available devices
- Custom vocabulary: User-defined glossary for post-processing
- Launch-at-login: Toggleable via ServiceManagement

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- None detected - all API calls are request/response based

## Network Behavior

**Requests Made:**
1. Transcription submission: POST to `https://api.groq.com/openai/v1/audio/transcriptions` with audio file (multipart form-data)
2. Post-processing: POST to `https://api.groq.com/openai/v1/chat/completions` with JSON payload
3. Update check: GET to `https://api.github.com/repos/zachlatta/freeflow/releases/latest`
4. Update download: GET to GitHub CDN URL for .dmg file (URL from release assets)
5. API validation: GET to `https://api.groq.com/openai/v1/models` with Bearer token

**All requests use standard URLSession with:**
- Timeout: 20 seconds for transcription/post-processing
- Cache policy: Reload ignoring cache for update checks
- Standard HTTP headers

**No data retention:**
- Audio files sent to Groq are not persisted locally after transcription
- All processing is ephemeral
- Pipeline history stored locally for UI reference only

---

*Integration audit: 2026-02-18*
