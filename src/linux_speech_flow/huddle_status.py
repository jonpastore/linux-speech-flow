import time
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib


class HuddleStatusWindow(Gtk.ApplicationWindow):
    """Live status display for an active Slack huddle recording session.

    Displays:
      - Elapsed huddle duration timer
      - Chunk count (N chunks recorded)
      - Last chunk transcript text (most recent transcribed chunk)
      - Confidence indicator for most recent chunk (green/yellow/red label)
      - Last executed voice command
      - Active command spinner (shown when bot is processing a command)
      - Recording mode badge: "MIC + SYSTEM"
      - Slack connection status dot (green/red label)
      - Workspace name + channel/DM name

    NOT included: pause-detection timer (not meaningful in huddle context).

    Created/destroyed by HuddleManager. Not user-closeable during recording.
    All update_* methods must be called from GTK main thread.
    """

    def __init__(self, application):
        super().__init__(application=application, title="Huddle Recording")
        self.set_default_size(400, 380)
        self.set_resizable(False)
        self.set_deletable(False)

        self._session_start: float | None = None
        self._elapsed_timer_id: int | None = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        self.set_child(box)

        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._mode_badge = Gtk.Label(label="MIC + SYSTEM")
        self._mode_badge.add_css_class("caption")
        self._slack_status_dot = Gtk.Label(label="● Slack: connecting...")
        header_row.append(self._mode_badge)
        header_row.append(Gtk.Label(label=" | "))
        header_row.append(self._slack_status_dot)
        header_row.set_hexpand(True)
        box.append(header_row)

        self._workspace_label = Gtk.Label(label="")
        self._workspace_label.set_xalign(0)
        self._workspace_label.add_css_class("caption")
        box.append(self._workspace_label)

        box.append(Gtk.Separator())

        self._elapsed_label = Gtk.Label(label="Duration: 0:00")
        self._elapsed_label.add_css_class("title-3")
        self._elapsed_label.set_xalign(0)
        box.append(self._elapsed_label)

        self._chunk_label = Gtk.Label(label="Chunks: 0")
        self._chunk_label.set_xalign(0)
        box.append(self._chunk_label)

        box.append(Gtk.Separator())

        transcript_title = Gtk.Label(label="Last Chunk Transcript")
        transcript_title.set_xalign(0)
        transcript_title.add_css_class("caption")
        box.append(transcript_title)

        self._transcript_label = Gtk.Label(label="\u2014")
        self._transcript_label.set_wrap(True)
        self._transcript_label.set_xalign(0)
        self._transcript_label.set_max_width_chars(45)
        self._transcript_label.add_css_class("card")
        box.append(self._transcript_label)

        conf_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        conf_lbl = Gtk.Label(label="Confidence:")
        conf_lbl.set_xalign(0)
        self._confidence_label = Gtk.Label(label="\u2014")
        conf_row.append(conf_lbl)
        conf_row.append(self._confidence_label)
        box.append(conf_row)

        box.append(Gtk.Separator())

        cmd_title = Gtk.Label(label="Last Command")
        cmd_title.set_xalign(0)
        cmd_title.add_css_class("caption")
        box.append(cmd_title)

        cmd_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._command_label = Gtk.Label(label="\u2014")
        self._command_label.set_xalign(0)
        self._command_spinner = Gtk.Spinner()
        cmd_row.append(self._command_label)
        cmd_row.append(self._command_spinner)
        box.append(cmd_row)

    def start_elapsed_timer(self) -> None:
        self._session_start = time.monotonic()
        self._elapsed_timer_id = GLib.timeout_add_seconds(1, self._tick_elapsed)

    def stop_elapsed_timer(self) -> None:
        if self._elapsed_timer_id is not None:
            GLib.source_remove(self._elapsed_timer_id)
            self._elapsed_timer_id = None

    def _tick_elapsed(self) -> bool:
        if self._session_start is None:
            return False
        elapsed = int(time.monotonic() - self._session_start)
        m, s = divmod(elapsed, 60)
        h, m = divmod(m, 60)
        if h:
            text = f"Duration: {h}:{m:02d}:{s:02d}"
        else:
            text = f"Duration: {m}:{s:02d}"
        self._elapsed_label.set_text(text)
        return True

    def update_chunk_count(self, count: int) -> None:
        self._chunk_label.set_text(f"Chunks: {count}")

    def update_transcript(self, text: str) -> None:
        self._transcript_label.set_text(text or "\u2014")

    def update_confidence(self, confidence: float | None) -> None:
        """confidence: 0.0-1.0 float or None. Colors: >=0.8 green, >=0.5 yellow, <0.5 red."""
        if confidence is None:
            self._confidence_label.set_text("\u2014")
            for cls in ("success", "warning", "error"):
                self._confidence_label.remove_css_class(cls)
            return
        pct = int(confidence * 100)
        self._confidence_label.set_text(f"{pct}%")
        for cls in ("success", "warning", "error"):
            self._confidence_label.remove_css_class(cls)
        if confidence >= 0.8:
            self._confidence_label.add_css_class("success")
        elif confidence >= 0.5:
            self._confidence_label.add_css_class("warning")
        else:
            self._confidence_label.add_css_class("error")

    def update_last_command(self, command: str) -> None:
        self._command_label.set_text(command or "\u2014")

    def set_command_processing(self, active: bool) -> None:
        if active:
            self._command_spinner.start()
        else:
            self._command_spinner.stop()

    def update_slack_status(self, connected: bool, workspace: str = "", channel: str = "") -> None:
        if connected:
            self._slack_status_dot.set_text("● Slack: connected")
            self._slack_status_dot.remove_css_class("error")
            self._slack_status_dot.add_css_class("success")
        else:
            self._slack_status_dot.set_text("● Slack: disconnected")
            self._slack_status_dot.remove_css_class("success")
            self._slack_status_dot.add_css_class("error")
        ws_text = ""
        if workspace:
            ws_text = workspace
            if channel:
                ws_text += f" \u2192 {channel}"
        self._workspace_label.set_text(ws_text)
