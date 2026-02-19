# Phase 1: Foundation & Configuration - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Project scaffolding, config persistence, and first-run GTK setup wizard. User installs, launches `linux-speech-flow`, completes a wizard (API key → mic → vocabulary), and all settings are persisted to `~/.config/linux-speech-flow/config.json`. The app is then ready for Phase 2 to build on. Audio, transcription, tray UI, and packaging are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Wizard flow & structure
- Multi-step wizard (one topic per step): API key → mic selection → vocabulary list
- If user closes/cancels before finishing: wizard reopens on next launch (no config = no run)
- After Finish: wizard closes, tray icon appears — setup complete
- Vocabulary step is optional; user can skip with an empty list and add words later via Settings
- Settings window (reopened from tray menu) re-uses or mirrors the wizard; exact mode (same widget vs. flat panel) is Claude's discretion — choose simplest GTK implementation

### API key validation
- Validate in two passes: format check first, then a live Groq API call (e.g., list models endpoint)
- Cannot advance past the API key step on failure — inline error, stay on same step
- Error messages distinguish between causes: "Invalid API key" vs. "Could not connect to Groq — check your internet connection"
- In-progress UX (spinner, disabled Next button) is Claude's discretion
- Field masking (show/hide toggle) is Claude's discretion

### Vocabulary list editing
- Config schema: flat list of strings — `["kubernetes", "OAuth", "linux-speech-flow"]`
- No constraints on entries — any text, any length, no validation
- UI input method (text area vs. tag chips) is Claude's discretion
- How vocabulary is used in the post-processing prompt (Phase 3) is Claude's discretion (e.g., exact spelling enforcement)

### App launch & entry point
- Launch command: `linux-speech-flow`
- Python package/module name: Claude's discretion (consistent with command, e.g., `linux_speech_flow`)
- Project structure: fresh Python project from scratch using `pyproject.toml` + `src/` layout
- Python version: 3.11+
- Config directory: `~/.config/linux-speech-flow/config.json` (with 0600 permissions)
- Data directory: `~/.local/share/linux-speech-flow/` (for future phases)
- Single-instance: if already running, silently ignore second launch (lock file or socket)
- Startup sequence on first run: wizard appears first → after Finish → tray starts

### Claude's Discretion
- GTK wizard layout (Gtk.Assistant vs. custom multi-page Gtk.Window)
- Spinner/loading UX during API key validation
- API key field masking implementation
- Vocabulary input widget (text area vs. tag-style)
- Python package name (recommend: `linux_speech_flow`)
- Vocabulary prompt strategy for Phase 3 (recommend: exact spelling enforcement)
- Settings window implementation (same widget reused vs. separate simple panel)

</decisions>

<specifics>
## Specific Ideas

- Launch command must be `linux-speech-flow` (not `freeflow` or `python -m ...`)
- Config path is `~/.config/linux-speech-flow/` (not `~/.config/freeflow/`)
- The app must be single-instance — silently ignore if already running

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation-and-configuration*
*Context gathered: 2026-02-19*
