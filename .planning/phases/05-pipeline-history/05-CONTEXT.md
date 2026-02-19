# Phase 5: Pipeline History - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

A GTK log viewer window (opened from the tray menu) showing the last N transcription runs stored in SQLite at ~/.local/share/linux-speech-flow/. Each run records: timestamp, raw transcript, processed transcript, window context (app + window title), and duration. The window is read-only history plus storage management. Search, editing, and export are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Log entry layout
- Compact rows as default: shows timestamp + duration + processed transcript preview (truncated)
- Newest-first ordering
- Click to expand inline — row grows below the compact row
- Expanded shows: full processed transcript, then raw transcript below it, plus app/window title and duration

### Transcript display
- Both processed and raw transcripts shown in the expanded row (raw below processed)
- Full text — scrollable within the row if long (no height cap)
- Color/background distinction between processed (primary) and raw (secondary/muted shade)
- Copy button per transcript section (one for processed, one for raw)

### Window behavior
- Live updates: new entries appear at the top as transcriptions complete, window stays usable
- Focus existing window if already open (single-instance)
- Persist window position + size between opens
- Window title: "linux-speech-flow — History"
- Tray menu item label: "Transcription History"

### Empty state
- Simple centered message: "No transcriptions yet. Press [hotkey] to start recording."
- Hotkey shown should reflect the current configured hotkey (read from settings)

### Interactions and storage management
- "Clear All History" button: available both in the history window header/toolbar AND in Settings
- Clearing logs requires a confirmation dialog: "Clear all transcription history? This cannot be undone." with Cancel / Clear buttons
- "Clear Temp Audio Files" button: in both history window footer AND Settings (Maintenance/Storage section)
- Max entries limit: configurable in Settings (default 20; user can raise/lower)
- Manual GC trigger: run cleanup on demand, available in both history window and Settings

### Extensibility note (Phase 6 Conversation Mode)
- Phase 6 will add conversation sessions to this same history window as a distinct row type
- The SQLite schema and history window must be designed to accommodate a second entry type with different fields (file path, AI confidence, resume status)
- Phase 5 does NOT implement conversation mode — but must not make the schema/window un-extendable

### Claude's Discretion
- Exact color/shade for background distinction between processed and raw
- Compact row preview truncation length
- Copy button icon vs label
- Exact layout of history window footer controls
- Settings section name for storage management (e.g. "Maintenance", "Storage", "History")

</decisions>

<specifics>
## Specific Ideas

- The empty state message should show the actual configured hotkey (dynamic, not hardcoded "F9")
- Storage management should feel like a "housekeeping" section — not prominent, but accessible

</specifics>

<deferred>
## Deferred Ideas

- **Rename FreeFlow → linux-speech-flow** — All tray title, icon names (freeflow-*), autostart .desktop, and app metadata use "FreeFlow" branding. User confirmed this should be "linux-speech-flow". Resolved as gap closure Phase 4.1 (to run before Phase 5).
- **Hotkey customization in Settings** — User wants to change recording hotkey from F9 to custom key combinations (e.g. Fn, Fn+R for replay). Requires Settings UI hotkey picker and HotkeyManager runtime reconfiguration. Significant scope — own phase.
- **Tray menu hotkey hints** — User requested the tray context menu show text indicating the current hotkeys for record start/stop and replay. Phase 4 tray enhancement.
- **Phase 6: Conversation Mode** — Long-form recording (Fn+C hotkey), silence-chunked transcription, auto-stop timers, multi-provider AI analysis (Groq/Grok/Claude/etc.), iterative Q&A loop until 95% confidence, coalesced file output (ISO8601 + AI-title.txt), speak-or-type answers, partial save with continuation prompt, resume from history window. Extends Phase 5's history window with conversation row type.
- **Slack integration** — Output to Slack, join Slack huddles as a bot. Future phase.

</deferred>

---

*Phase: 05-pipeline-history*
*Context gathered: 2026-02-21*
