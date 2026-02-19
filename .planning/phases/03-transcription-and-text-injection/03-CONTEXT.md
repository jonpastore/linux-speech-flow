# Phase 3: Transcription & Text Injection - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Background pipeline: WAV file in → Groq Whisper transcription → Groq LLM post-processing with window context → clipboard paste into focused application. User's touchpoints are the audible feedback during the wait and the text that appears. No new UI beyond settings additions and the F10 reprocess dialog.

Phase 2's `_on_recording_complete` callback hands off the WAV file path to Phase 3's pipeline. Phase 3 must consume (and clean up) the WAV before the callback returns — or hand off WAV path asynchronously so the recording thread can be released.

</domain>

<decisions>
## Implementation Decisions

### Post-processing style
- **Smart cleanup**: strip filler words (um, uh, like), fix repetitions, improve sentence flow — preserve meaning, do not paraphrase
- Preserve the user's casing intent; do not auto-capitalize unless clearly a sentence start
- Add terminal punctuation only if output is clearly a complete sentence; leave fragments unpunctuated
- Voice commands treated as formatting: "new line" → `\n`, "new paragraph" → `\n\n` in output
- Design for both short (one-sentence) and long (multi-paragraph) dictation in the same prompt
- LLM prompt is user-editable in settings (advanced section, with warnings about breaking behaviour)
- Custom vocabulary prompt injection: Claude's Discretion (design the injection strategy)

### Window context usage
- Detect app category (terminal emulator, code editor, other) from active window class/title
- App category list is **configurable** in settings — user can add/override entries; ship with sensible defaults for common terminals (gnome-terminal, kitty, alacritty, xterm, konsole) and editors (code, vim, neovim, emacs, sublime_text, gedit)
- Terminal emulators: use Ctrl+Shift+V for paste
- Code editors: detected for LLM context; paste method and prompt adaptation: Claude's Discretion
- How window context feeds into the LLM prompt: Claude's Discretion
- Fallback when xdotool cannot detect active window (Wayland, locked screen): Claude's Discretion

### Error & edge case handling
- Whisper API failure: play error sound (distinct chime, not stop sound) + desktop notification with **specific** message (separate text for: invalid API key / network error / rate limit exceeded)
- Silence or transcript too short to be meaningful: notify user (no paste, no sound)
- LLM post-processing failure: paste raw Whisper transcript as fallback + subtle notification "LLM failed — raw transcript pasted"
- Retry strategy: **Fibonacci-scaled**, starting at 5 s, up to **5 attempts** (5 s, 8 s, 13 s, 21 s, 34 s) before giving up
- After all retries exhausted: save WAV to `~/.local/share/linux-speech-flow/failed/` (filename includes timestamp)
- Error notification informs user WAV was saved and F10 can reprocess

### F10 reprocess hotkey (new capability — requires new requirement IDs)
- F10 is the reprocess hotkey; behaviour:
  - **1 failed WAV**: retry pipeline immediately, paste as normal
  - **Multiple failed WAVs**: open a small GTK dialog listing recordings by timestamp; user selects one or all
- "Reprocess All" batch mode: prompt user before starting — "Write all to file" or "Paste each into current window" (sequential)
- Failed WAV storage: `~/.local/share/linux-speech-flow/failed/`; cleaned up on successful reprocess
- Tray indicator for pending failed recordings: **deferred to Phase 4**

### Feedback during wait
- Audio sequence per successful run: stop chime (Phase 2, already done) → **processing sound** (one-shot, plays on F9 release) → **success chime** (plays when text is pasted)
- Both processing.wav and success.wav are new bundled files added to `src/linux_speech_flow/sounds/`
- All three sounds individually toggleable in settings (Phase 2 start/stop already configurable; Phase 3 adds processing/success toggles)
- Pipeline timeout: **60 seconds** (default), configurable in settings
- F9 pressed while pipeline is running: **queue** the new recording; notify user "Recording queued (N pending)" when queued
- Queue processes in FIFO order; each item goes through the full pipeline and pastes in sequence

### Settings — new Transcription section
- Add a dedicated **Transcription** tab/section to SettingsWindow alongside the existing Audio section
- Fields in the Transcription section:
  - Groq LLM model selector (default = best performer, e.g. `meta-llama/llama-4-scout-17b-16e-instruct`; user can override)
  - Pipeline timeout (default: 60 s)
  - Sound toggles: processing sound on/off, success chime on/off
  - App category list editor (terminals / code editors)
  - Advanced: LLM system prompt editor (clearly labelled "Advanced — changing this may break post-processing", with a Reset to Default button)

### Claude's Discretion
- How window context is embedded in the LLM post-processing prompt
- Custom vocabulary injection strategy in the prompt
- Code editor paste method (Ctrl+V assumed sufficient unless research shows otherwise)
- Fallback logic when active window cannot be detected
- Exact WAV file naming convention in the failed/ directory
- Retry applies to both Whisper and LLM calls individually or pipeline-wide (design the retry scope)
- Groq Whisper model version (default recommendation based on research)

</decisions>

<specifics>
## Specific Ideas

- "new line" and "new paragraph" as spoken formatting commands must be handled in the LLM prompt, not post-hoc in Python — the LLM needs to know to interpret them
- App category configuration should feel like a simple table (app name pattern → category), not a complex UI
- The GTK reprocess dialog should be minimal — timestamp list with checkboxes, "Reprocess Selected" and "Reprocess All" buttons
- Project name is **linux-speech-flow** throughout (note: REQUIREMENTS.md and config paths still say "freeflow" — update these paths in Phase 3 config defaults: `~/.config/linux-speech-flow/config.json`, `~/.local/share/linux-speech-flow/`)

</specifics>

<deferred>
## Deferred Ideas

- Tray icon state change during transcription (processing indicator) — Phase 4 (tray is Phase 4 scope)
- Tray indicator for pending failed recordings — Phase 4
- KPI tracking per transcription run (model used, latency, Whisper confidence score) — Phase 5 (Pipeline History already tracks duration/context; extend there)
- Multi-model A/B comparison to determine best Groq LLM output — Phase 5 or standalone phase

## New Requirements Needed

The following capabilities were defined during discussion and require new requirement IDs before planning:

- **TRANS-07** (new): F10 reprocess hotkey for failed WAV files (single-file auto-retry, multi-file GTK dialog)
- **TRANS-08** (new): Failed WAV persistence to `~/.local/share/linux-speech-flow/failed/` on retry exhaustion
- **TRANS-09** (new): Batch reprocess mode — "write to file" or "paste to current window" selection
- **TRANS-10** (new): Processing sound (one-shot) and success chime (new bundled WAV files, individually toggleable)
- **TRANS-11** (new): Recording queue when F9 pressed during active pipeline; user notified of queue depth
- **CONF-XX** (new): Configurable Groq LLM model in Transcription settings (default = best performer)
- **CONF-XX** (new): Pipeline timeout configurable in Transcription settings (default: 60 s)
- **CONF-XX** (new): Configurable app category list (terminals, code editors) for paste behaviour and LLM context

</deferred>

---

*Phase: 03-transcription-and-text-injection*
*Context gathered: 2026-02-19*
