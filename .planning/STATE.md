---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-03-04T00:00:02.406Z"
progress:
  total_phases: 11
  completed_phases: 8
  total_plans: 40
  completed_plans: 39
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** Hold a key, speak, release -- transcribed text appears in whatever you're typing in.
**Current focus:** Phase 7 — Hotkey Customization

## Current Position

Phase: 7 of 9 — In Progress
Plan: 2/4 complete (07-02 done)
Status: Phase 7 plan 02 complete — Hotkeys section added to SettingsWindow with press-to-capture state machine, conflict/danger detection, per-hotkey and Reset All buttons, apply_binding_override for immediate hot-reload
Last activity: 2026-03-03 -- Executed plan 07-02; GNOME-style hotkey capture UI in Settings

Progress: [█████████████████████████████] 92%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 2 min
- Total execution time: 0.1 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation & Configuration | 4/5 | 9 min | 2 min |

**Recent Trend:**
- Last 5 plans: 3 min, 2 min, 1 min, 3 min
- Trend: stable

*Updated after each plan completion*

| Phase 02-audio-capture-and-hotkey P01 | 2 min | 2 tasks | 4 files |
| Phase 02-audio-capture-and-hotkey P02 | 2 min | 2 tasks | 7 files |
| Phase 02-audio-capture-and-hotkey P03 | 2 min | 1 task | 1 file |
| Phase 02-audio-capture-and-hotkey P04 | 1 min | 2 tasks | 2 files |
| Phase 02-audio-capture-and-hotkey P05 | 15 min | 2 tasks | 3 files |
| Phase 03-transcription-and-text-injection P01 | 1 | 2 tasks | 6 files |
| Phase 03 P02 | 3 | 2 tasks | 3 files |
| Phase 03-transcription-and-text-injection P03 | 1 | 1 tasks | 1 files |
| Phase 03 P04 | 2 | 1 tasks | 2 files |
| Phase 03-transcription-and-text-injection P05 | 2 | 2 tasks | 2 files |
| Phase 04-system-tray-and-desktop-integration P01 | 1 | 2 tasks | 10 files |
| Phase 04-system-tray-and-desktop-integration P02 | 2 | 2 tasks | 3 files |
| Phase 04-system-tray-and-desktop-integration P03 | 30 | 2 tasks | 3 files |
| Phase 04.1 P02 | 1 | 2 tasks | 2 files |
| Phase 04.1 P03 | 1 | 1 tasks | 0 files (git history rewrite) |
| Phase 04.1-freeflow-rename-and-codebase-cleanup P03 | 2 | 2 tasks | 0 files |
| Phase 05-pipeline-history P01 | 1 | 2 tasks | 2 files |
| Phase 05-pipeline-history P02 | 1 | 1 tasks | 1 files |
| Phase 05-pipeline-history P03 | 2 | 2 tasks | 4 files |
| Phase 06-conversation-mode P01 | 3 min | 2 tasks | 7 files |
| Phase 06-conversation-mode P02 | 1 | 1 tasks | 1 files |
| Phase 06-conversation-mode P03 | 1 min | 1 tasks | 1 files |
| Phase 06-conversation-mode P04 | 2 min | 2 tasks | 2 files |
| Phase 06-conversation-mode P05 | 1 min | 1 tasks | 1 files |
| Phase 06-conversation-mode P05 | 1 | 1 tasks | 1 files |
| Phase 06-conversation-mode P06 | 2 | 2 tasks | 2 files |
| Phase 06-conversation-mode P07 | 2 | 2 tasks | 3 files |
| Phase 06-conversation-mode P08 | 5 min | 2 tasks | 0 files (verification only) |
| Phase 07-hotkey-customization P01 | 6 | 3 tasks | 4 files |
| Phase 07-hotkey-customization P02 | 4 | 1 tasks | 3 files |
| Phase 07-hotkey-customization P03 | 5 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Use pasimple over sounddevice for audio (PortAudio 19.6.0 cannot enumerate PulseAudio/PipeWire devices)
- [Roadmap]: Clipboard paste only via xclip + xdotool Ctrl+V (xdotool type breaks on non-ASCII)
- [Roadmap]: Try/except for AppIndicator3 vs AyatanaAppIndicator3 (distro-dependent)
- [Roadmap]: XDG autostart .desktop entry, not systemd user service (systemd lacks DISPLAY/DBUS env vars)
- [Roadmap]: Bundled venv in .deb via dh-virtualenv or fpm (PEP 668 blocks system pip on Ubuntu 24.04+)
- [01-01]: Python 3.10 (system) used for venv base; gi/PyGObject only compiled for system Python 3.10, not pyenv 3.11
- [01-01]: requires-python set to >=3.10 (adjusted from >=3.11) to match system Python with gi bindings
- [01-01]: pulsectl per-call context manager pattern for safe PulseAudio connection lifecycle
- [01-01]: Gtk.Application FLAGS_NONE for D-Bus single-instance enforcement
- [Phase 01]: _path keyword-only parameter for test injection keeps production API clean and avoids monkeypatching module globals
- [Phase 01]: pytest installed directly in .venv (not pyproject.toml dev deps) to keep .deb production dependencies minimal
- [01-03]: gsk_ prefix + min 20 chars as format check for Groq keys; simple and covers all real key shapes
- [01-03]: ConnectionError and Timeout share one message — both mean network unreachable to the user
- [01-03]: No new pyproject.toml dependencies; requests already declared in 01-01
- [01-04]: Flat layout for SettingsWindow (not wizard reuse with settings_mode flag) — simpler, no wizard nav state
- [01-04]: list_microphones() called on page/window entry, not __init__, for re-enumeration support
- [01-04]: GLib.idle_add callback must return False to avoid re-invocation
- [Phase 02-01]: list_sinks() swallows PulseError and returns [] for graceful degradation to default sink
- [Phase 02-01]: No config migration code needed — load_config() dict merge already backfills Phase 2 defaults into Phase 1 configs
- [Phase 02-01]: test_save_load_round_trip updated to key-presence check rather than strict equality — correct contract for default-merging load_config()
- [02-02]: play_sound() placed in sounds/__init__.py (not sounds.py) — Python cannot have both module and package with same name in same directory
- [02-02]: importlib.resources.files() for bundled WAV paths (not __file__) — works in installed .deb/wheel packages
- [02-02]: send_notification() returns None gracefully when notify-send missing or -p unsupported
- [02-03]: device_name uses 'or None' to coerce empty string to None for PulseAudio default source
- [02-03]: PaSimpleError wraps entire pasimple context block (covers stream open + mid-read disconnects)
- [02-03]: MIN_SILENCE_GUARD_CHUNKS=10 prevents false silence trigger on PulseAudio buffer fill latency at start
- [02-03]: WAV written incrementally per chunk (not buffered) to support long recordings
- [02-04]: suppress=True NOT used on pynput Listener — would crash X11 sessions (pynput issue #269)
- [02-04]: _on_recorder_complete plays stop.wav before calling on_complete_cb so auto-stop paths play descending chime per CONTEXT.md Area 2
- [02-04]: mark_started() guard (called via GLib.idle_add after first GTK tick) prevents F9 held at app startup from triggering recording
- [02-05]: Toggle mode (F9 start, ESC stop) chosen over hold-to-record — hold-to-record impractical for real dictation sessions
- [02-05]: do_startup/do_shutdown use Gtk.Application.do_startup(self) explicitly — super() segfaults under PyGObject on Python 3.10
- [02-05]: Stop chime only in _on_recorder_complete, not _stop_recording — prevents double chime on all stop paths
- [02-05]: WAV temp file cleanup in _on_recording_complete Phase 2 stub — Phase 3 must consume WAV before callback returns
- [02-05]: Mic moved into Audio section of settings for logical grouping; spinner scroll blocked to prevent accidental changes
- [Phase 03]: groq>=1.0.0 declared in pyproject.toml — covers Whisper transcription and LLM post-processing via single SDK
- [Phase 03]: Phase 3 config keys use dict merge backfill — no migration code needed for existing user configs
- [Phase 03]: processing.wav uses C5->E5 ascending two-note; success.wav uses C5->E5->G5 three-note fanfare for distinct completion sound
- [Phase 03]: groq client max_retries=0: Fibonacci wrapper is sole retry mechanism to prevent 10x total attempts
- [Phase 03]: Window context captured at submit() on GTK main thread to prevent focus-theft from notification stealing window ID
- [Phase 03]: Wayland paste: wl-copy for clipboard, skip keystroke injection (ydotoold not required), notify user to paste manually
- [Phase 03-03]: Gtk.Entry (not ComboBoxText) for LLM model — user may type any model string supported by Groq
- [Phase 03-03]: Gtk.Expander for advanced prompt section with warning text to discourage casual edits
- [Phase 03]: Lazy import of reprocess_dialog.py inside _on_reprocess_hotkey body — deferred import avoids ImportError at startup before Plan 05 creates the module
- [Phase 03]: Gtk.Window + set_modal(True) instead of Gtk.Dialog — Gtk.Dialog deprecated since GTK 4.10
- [Phase 03]: batch_output_path field in window_info dict overrides normal paste to file append — zero-overhead signal, no new queue type
- [Phase 03]: xdg-open fires on queue empty heuristic after last batch WAV — pragmatic for serial FIFO processing
- [Phase 04-system-tray-and-desktop-integration]: trayer==0.1.1 pinned; install_icons() always overwrites; DBusGMainLoop in TrayManager.__init__; left-click opens Settings (SNI right-click always shows menu)
- [04-02]: sys.executable used for autostart Exec= path (simpler and always resolves to running venv Python)
- [04-02]: on_recording_start fires after state=RECORDING set, before config load and AudioRecorder start (tray shows recording immediately)
- [04-02]: _notify_failed_count() called after try/except for os.unlink in _process() — fresh glob always reflects actual dir state
- [04-03]: Verification-phase UX fixes (SVG icons, trayer IconThemePath, settings Cancel/Esc/unsaved-changes) applied as deviation Rules 2-3 during human sign-off session
- [04-03]: All TRAY-01 through TRAY-04 requirements satisfied across plans 04-01, 04-02, 04-03; Phase 4 complete
- [04.1-01]: freeflow cleanup stubs (old_icon_stems in tray.py, old_desktop in app.py) intentionally retain old names to remove orphaned installed artifacts
- [04.1-01]: git mv used for all 8 SVG renames to preserve rename history and keep pyproject.toml package-data glob clean
- [Phase 04.1]: [04.1-02]: shutil.copy2 + rmtree for config migration; import logging inside except block to avoid circular import
- [04.1-03]: git reset --soft <root> + commit --amend pattern squashes all 97 commits into single "Initial commit: Linux Speech Flow"; untracked files (venv, pycache) present in porcelain output do not block squash
- [Phase 04.1]: git reset --soft to root + amend pattern squashes 97 commits into single 'Initial commit: Linux Speech Flow'; untracked files do not block squash
- [Phase 05-01]: Per-call connection pattern: HistoryStore._connect() called fresh in each method — thread-safe by design without locks
- [Phase 05-01]: Safe subquery prune form: DELETE WHERE id NOT IN (SELECT id ... LIMIT ?) avoids SQLITE_ENABLE_UPDATE_DELETE_LIMIT dependency
- [Phase 05-01]: entry_type + extra_json columns added in Phase 5 schema for Phase 6 conversation-mode extensibility without migration
- [Phase 05-02]: Gtk.ListBox selection_mode=NONE with row-activated toggle: rows manage own expand state
- [Phase 05-02]: Closure capture (t=text) in Copy button lambda prevents late-binding bug
- [Phase 05-02]: Gtk.Window(modal=True) not Gtk.Dialog: matches project pattern (GTK 4.10 deprecation)
- [Phase 05-03]: HistoryStore.insert() called on worker thread inside _process() before GLib.idle_add — DB write never on GTK main thread
- [Phase 05-03]: started_at captured at top of _process() before any API calls — measures total pipeline duration including Whisper + LLM
- [Phase 05-03]: history_max_entries read from config per-call in _process() — always uses current setting without restart
- [Phase 05-04]: SQLite VACUUM must run outside any active transaction; clear_all() committed DELETE first then called VACUUM separately to avoid rollback undoing the delete
- [Phase 05-04]: gtk-update-icon-cache must be called after install_icons() renames icons; stale OS icon theme cache reverts tray to old icon without invalidation
- [06-01]: conv_hotkey_start defaults to f11 (not Fn+C): Fn key combos are hardware-firmware intercepted on Linux and never reach the OS input layer; f11 is the practical substitute; Phase 7 makes this configurable
- [06-01]: conv_hotkey_feedback defaults to f12 (not Fn+D): same Fn key Linux limitation
- [06-01]: F11 during _STATE_RECORDING is silently ignored (IDLE-guard) — prevents accidental conversation start mid-dictation
- [06-01]: openai upgraded to 2.21.0 in venv (system had 0.27.5) to get 1.x API for Grok xAI base_url override
- [Phase 06-02]: ConversationRecorder standalone class (not AudioRecorder subclass): chunked multi-chunk model requires separate architecture from single-file AudioRecorder
- [06-03]: Deferred openai/google.genai imports inside _call_grok/_call_gemini — avoids ImportError at startup when packages not installed or keys not configured
- [06-03]: synthesize() falls back to first non-error model result if meta-model call fails — prevents total analysis failure
- [06-03]: coalesce_file() omits ## Q&A section entirely when qa_rounds is empty — no empty headers in output files
- [06-03]: continue_qa() delegates to analyze() — Q&A refinement uses same ThreadPoolExecutor fan-out path as initial analysis
- [06-04]: ConversationStatusWindow imported lazily inside _show_status_window to avoid circular import risk
- [06-04]: silence_stop timer created inside _on_silence_warn callback (not pre-created) — ensures timer only starts after warn fires
- [06-04]: stop_session defers _finish_session 500ms via GLib.timeout_add to allow last chunk GLib.idle_add to flush before transcript assembly
- [06-04]: Gtk.Window(modal=True) used for silence warning dialog — consistent with project pattern avoiding deprecated Gtk.Dialog (GTK 4.10)
- [Phase 06-05]: Paned divider set to 280px with set_resize_start_child(False) so left panel stays fixed and right panel expands on resize
- [Phase 06-05]: on_continue_qa button only rendered if callback is non-None — viewer works standalone without Q&A feature
- [Phase 06-06]: ConversationDialog _on_submit fallback always includes groq if no model selected; Speak button fills answer entry for review not auto-submit; confidence >= 0.95 requires explicit user confirmation before _finalise runs
- [Phase 06-07]: ConversationManager instantiated before TrayManager in do_startup() — on_tray_state uses lazy lambda to defer self._tray lookup until call time
- [Phase 06-07]: Conversation History tray item added as second item after Transcription History for logical grouping
- [Phase 06-07]: Settings dirty tracking extended to all Phase 6 widgets so unsaved-changes dialog triggers correctly for Conversation Mode fields
- [06.1-01]: on_silence_tick emits raw silence_frames (not seconds) — manager converts to seconds using CHUNK_DURATION, keeping recorder concern-free of display logic
- [06.1-01]: Debounce sentinel last_emitted_silence = -1 ensures first tick (silence_frames=0) always fires rather than being suppressed
- [06.1-01]: update_silence/update_transcript placed before _update_elapsed to group public API together in ConversationStatusWindow
- [06.1-02]: Cross-chunk silence accumulation via _silence_offset_sec: when silence_frames goes backwards (new chunk after boundary), prior chunk's count carried forward; voice detection (silence_frames==0) resets both offset and last value
- [06.1-02]: GTK 'card' CSS class for transcript container gives native GNOME appearance without custom CSS; maintained by libadwaita design system
- [Phase 07-01]: _MODIFIER_MAP built as instance attr in __init__ (not class-level const) so mocked keyboard.Key refs are captured at instantiation time
- [Phase 07-01]: _matches_binding checks len(key_id)==1 before Key enum lookup to avoid MagicMock always returning truthy on [] access
- [Phase 07-01]: record binding checked before stop in _on_press so Ctrl+Alt+R while RECORDING uses _stop_recording_hotkey (stop_was_hotkey=True)
- [Phase 07-01]: parse_combo and combo_display are module-level functions for Settings UI import without needing HotkeyManager instance
- [Phase 07-02]: set_focus(None) clears GTK focus from capture button so window-level EventControllerKey receives key events
- [Phase 07-02]: apply_binding_override updates in-memory _bindings dict directly for pre-save hot-reload; reload_bindings() remains full config-sync path on settings close
- [Phase 07-02]: Lazy _GTK_MODIFIER_KEYSYMS via try/except NameError inside _handle_capture_key prevents Gdk import before gi.require_version guarantee
- [Phase 07-02]: Canonical modifier order enforced in _handle_capture_key combo_str construction to match DANGEROUS_COMBOS frozenset exactly
- [Phase 07-03]: TestSettingsCaptureStateMachine uses _make_sim() closures to test the capture state machine without GTK
- [Phase 07-03]: test_matches_binding_special_key configures mock_kb.Key.__getitem__ to match attribute access, fixing mock equality gap

### Roadmap Evolution

- Phase 6 added: Conversation Mode (long-form recording, AI analysis, iterative Q&A)
- Phase 7 added: Hotkey Customization (configurable hotkeys in Settings)
- Phase 8 added: Slack Integration (output to Slack, join Slack huddles as bot)
- Phase 9 added: Packaging & Distribution (moved from Phase 6 to prioritize features first)
- Phase 4.1 inserted after Phase 4 (URGENT): FreeFlow rename and codebase cleanup — branding rename, temp file leak fixes, VU meter dedup, dead config key removal

### Pending Todos

None.

### Blockers/Concerns

- Validate pasimple is actively maintained and supports mic selection/device enumeration before committing to it in Phase 2
- Test AppIndicator extension default state on fresh Pop!_OS install before Phase 4
- [Phase 06 — active]: Silence timer fires too aggressively during conversation recording — 180s warn triggered while user was actively speaking. Likely cause: silence detection RMS threshold in ConversationRecorder is too sensitive (treating low-energy speech as silence), causing chunk gaps that reset the timer incorrectly. Needs investigation before Phase 6 sign-off.

## Session Continuity

Last session: 2026-03-03
Stopped at: Completed 07-02-PLAN.md — Hotkeys section in SettingsWindow with press-to-capture state machine
Resume file: .planning/phases/07-hotkey-customization/.continue-here.md
