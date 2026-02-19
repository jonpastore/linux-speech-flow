# Phase 4: System Tray & Desktop Integration - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

A persistent AppIndicator3 system tray icon that represents the app's presence, shows its current pipeline state, and provides a menu for accessing settings, debug log, reprocess, and quit. No new recording or transcription logic — this phase wraps Phase 3's pipeline in a proper desktop shell.

</domain>

<decisions>
## Implementation Decisions

### Tray icon states
- 4 states: idle (grey) / recording (red pulse) / processing (yellow spin) / error (red with X)
- Recording and processing states are animated — frame-swapping via GLib.timeout_add timer
- Error state clears automatically when user presses F9 to start a new recording
- Error state is set by any Whisper API failure (auth error, network error, rate limit)

### App window behavior
- Remove the placeholder window entirely — app runs headless in Phase 4
- App stays alive via `Gtk.Application.hold()` (prevents auto-quit when no windows open)
- Left-click on tray icon opens Settings window (trayer SNI protocol constraint: `secondary-activate` is not reliably fired by trayer, so left-click is used for Settings as the primary action; right-click opens the menu — this overrides the original discussion preference of left=menu/right=Settings)
- Quit is only available via the tray menu (no window close button)
- Add XDG autostart `.desktop` file to `~/.config/autostart/` for development use, pointing to the venv Python

### Tray menu contents and order
- Flat menu, no separators: Settings / Open Debug Log / Reprocess Failed (N) / Quit
- "Reprocess Failed (N)" shows live count of WAVs in the failed/ directory
- "Reprocess Failed" is greyed out when count is 0
- Count updates in real-time: pipeline calls a callback when a WAV is saved to failed/ or cleared after reprocess
- "Reprocess Failed" triggers the same F10 logic as the hotkey (single WAV = auto-paste, multiple = dialog)

### Claude's Discretion
- Animation frame count, frame rate, and SVG icon design for each state
- Implementation of right-click Settings (secondary-activate vs alternative approach)
- Mechanism for passing failed-count change callback from TranscriptionPipeline to TrayManager
- Whether to use icon theme names or direct SVG file paths for AppIndicator3
- AppIndicator3 vs AyatanaAppIndicator3 try/except fallback (already decided in STATE.md)

</decisions>

<specifics>
## Specific Ideas

- The XDG autostart `.desktop` file is for development convenience only — Phase 6 replaces it with a proper postinst-installed entry
- The `Exec=` line in the `.desktop` file should use the absolute venv Python path for development; Phase 6 will replace with `/usr/bin/linux-speech-flow` (installed binary)
- Real-time failed count means TrayManager needs to receive an `on_failed_count_changed` callback or watch the failed directory

</specifics>

<deferred>
## Deferred Ideas

- **CLI binary (`/usr/bin/linux-speech-flow`)** — Phase 6: `dh-virtualenv` bundles venv inside .deb, `postinst` creates system binary wrapper. No manual venv activation needed.
- **Installer script for .deb** — Phase 6: `postinst` registers autostart `.desktop`, creates binary, sets permissions
- **Bundled venv in .deb** — Phase 6: `dh-virtualenv` or `fpm` approach already in ROADMAP.md
- **View Run Log tray menu item** — Phase 5 (Pipeline History delivers the history viewer)

</deferred>

---

*Phase: 04-system-tray-and-desktop-integration*
*Context gathered: 2026-02-21*
