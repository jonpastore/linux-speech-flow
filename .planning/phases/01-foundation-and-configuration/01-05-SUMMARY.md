# Plan 01-05 Summary: Human Verification of Phase 1

## Status: COMPLETE

## What Was Verified

All 10 human-verification tests passed after several iterative fixes during the verification session.

## Test Results

| Test | Description | Result |
|------|-------------|--------|
| 1 | First-run wizard appears | PASS |
| 2 | API key validation blocks on invalid format | PASS |
| 3 | Network error shown correctly | PASS |
| 4 | Real key validates and advances to mic step | PASS |
| 5 | Microphone list shows real sources (no monitors) | PASS |
| 6 | Vocabulary step skippable (empty list ok) | PASS |
| 7 | Config persisted at correct path with 0600 perms | PASS |
| 8 | Second launch ignored (D-Bus single instance) | PASS |
| 9 | Settings window shows saved values, VU meter works | PASS |
| 10 | Wizard reappears when setup_complete=false | PASS |

## Bugs Found and Fixed During Verification

1. **`set_placeholder_text` missing on GTK 4.6** — `Gtk.PasswordEntry` doesn't expose `set_placeholder_text` in GTK 4.6; fixed with `set_property("placeholder-text", ...)` in both wizard.py and settings.py.

2. **No success feedback on API key validation** — Added "✓ API key valid." label to wizard and settings validation flow.

3. **VU meter segfault (wizard)** — pulsectl uses libpulse which is not thread-safe with GTK's GLib mainloop; replaced with parec subprocess + raw PCM reading via struct/math + GLib.idle_add.

4. **Tech stack presets missing from vocabulary page** — Added `TECH_STACKS` dict (13 presets) with ComboBoxText dropdown + "Add" button that deduplicates terms when appending to the vocabulary textarea.

5. **Mouse wheel scrolls mic dropdown** — Added `_block_scroll` helper using `Gtk.EventControllerScroll` returning True to suppress scroll events on ComboBoxText in both wizard.py and settings.py.

6. **No VU meter in settings window** — Added parec-based VU meter to SettingsWindow (same approach as wizard).

7. **Settings VU meter unresponsive** — Root cause: `SettingsWindow` inherited `Gtk.Window` instead of `Gtk.ApplicationWindow`; `GLib.idle_add` callbacks from background threads are only guaranteed to dispatch when `Gtk.ApplicationWindow` is used. Secondary cause: VU meter was started in `__init__` before `present()` — fixed by deferring via `GLib.idle_add(self._restart_vu_meter)`. Also added `handler_block/unblock` during combo population to prevent double-start race condition.

8. **Settings window opens multiple instances** — Added `_settings` instance tracking in `App` with `close-request` handler to clear reference on close.

## Decisions Made

- **SettingsWindow base class**: Changed to `Gtk.ApplicationWindow` to ensure GLib.idle_add dispatches correctly from VU worker thread
- **VU meter pattern**: thread + GLib.idle_add (not GLib.timeout_add poll) — this is the canonical PyGObject threading pattern
- **VU start timing**: Deferred via `GLib.idle_add` so it runs after window is presented/mapped, not during `__init__`
- **Scroll block**: `Gtk.EventControllerScroll` with VERTICAL flag, returning True from scroll handler — blocks wheel on all ComboBoxText dropdowns
