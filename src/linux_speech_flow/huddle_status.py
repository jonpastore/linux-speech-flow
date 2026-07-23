import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from linux_speech_flow.config import load_config


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

    def __init__(self, application, on_threshold_changed=None):
        super().__init__(application=application, title="Huddle Recording")
        self.set_default_size(420, 440)
        self.set_resizable(False)
        self.set_deletable(False)

        self._session_start: float | None = None
        self._elapsed_timer_id: int | None = None
        self._redraw_timer_id: int | None = None
        self._on_threshold_changed = on_threshold_changed
        config = load_config()
        self._silence_threshold = config.get("conv_silence_rms_threshold", 0.005)
        self._mic_level = 0.0

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

        self._mic_canvas = Gtk.DrawingArea()
        self._mic_canvas.set_hexpand(True)
        self._mic_canvas.set_size_request(-1, 14)
        self._mic_canvas.set_draw_func(self._draw_mic, None)
        box.append(self._mic_canvas)

        thresh_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        thresh_label = Gtk.Label(label="Threshold:")
        thresh_label.add_css_class("caption")
        thresh_box.append(thresh_label)
        self._thresh_slider = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.001, 0.05, 0.001
        )
        self._thresh_slider.set_value(self._silence_threshold)
        self._thresh_slider.set_hexpand(True)
        self._thresh_slider.set_draw_value(False)
        self._thresh_slider.connect("value-changed", self._on_thresh_slider)
        thresh_box.append(self._thresh_slider)
        box.append(thresh_box)

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

        box.append(Gtk.Separator())

        ctrl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ctrl_row.set_homogeneous(True)

        self._pause_button = Gtk.Button(label="Pause")
        self._pause_button.connect("clicked", self._on_pause_clicked)
        ctrl_row.append(self._pause_button)

        self._stop_button = Gtk.Button(label="Stop")
        self._stop_button.add_css_class("destructive-action")
        self._stop_button.connect("clicked", self._on_stop_clicked)
        ctrl_row.append(self._stop_button)

        self._analyze_button = Gtk.Button(label="Analyze")
        self._analyze_button.set_sensitive(False)
        self._analyze_button.connect("clicked", self._on_analyze_clicked)
        ctrl_row.append(self._analyze_button)

        self._exit_button = Gtk.Button(label="Exit")
        self._exit_button.connect("clicked", self._on_exit_clicked)
        ctrl_row.append(self._exit_button)

        box.append(ctrl_row)

        self._on_analyze_cb = None
        self._on_pause_cb = None
        self._on_resume_cb = None
        self._on_stop_cb = None
        self._on_exit_cb = None
        self._is_paused = False

    def set_on_analyze(self, callback) -> None:
        self._on_analyze_cb = callback

    def set_on_pause(self, callback) -> None:
        self._on_pause_cb = callback

    def set_on_resume(self, callback) -> None:
        self._on_resume_cb = callback

    def set_on_stop(self, callback) -> None:
        self._on_stop_cb = callback

    def set_on_exit(self, callback) -> None:
        self._on_exit_cb = callback

    def update_pause_state(self, paused: bool) -> None:
        self._is_paused = paused
        self._pause_button.set_label("Resume" if paused else "Pause")

    def _on_analyze_clicked(self, _button) -> None:
        if self._on_analyze_cb:
            self._on_analyze_cb()

    def _on_pause_clicked(self, _button) -> None:
        if self._is_paused:
            if self._on_resume_cb:
                self._on_resume_cb()
        else:
            if self._on_pause_cb:
                self._on_pause_cb()

    def _on_stop_clicked(self, _button) -> None:
        if self._on_stop_cb:
            self._on_stop_cb()

    def _on_exit_clicked(self, _button) -> None:
        if self._on_exit_cb:
            self._on_exit_cb()
        self.close()

    def update_mic_level(self, level: float) -> None:
        self._mic_level = level

    def set_threshold_from_calibration(self, value: float) -> None:
        self._silence_threshold = value
        self._thresh_slider.set_value(value)

    def _on_thresh_slider(self, slider) -> None:
        value = slider.get_value()
        self._silence_threshold = value
        if self._on_threshold_changed:
            self._on_threshold_changed(value)

    def _draw_mic(self, area, cr, width, height, _data) -> None:
        from linux_speech_flow.conversation_recorder import RMS_DISPLAY_SCALE

        cr.set_source_rgba(0.2, 0.2, 0.2, 0.4)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        thresh_x = min(1.0, self._silence_threshold * RMS_DISPLAY_SCALE) * width
        fill_w = self._mic_level * width
        if fill_w > 0:
            if fill_w <= thresh_x:
                cr.set_source_rgba(0.2, 0.5, 1.0, 0.8)
                cr.rectangle(0, 0, fill_w, height)
                cr.fill()
            else:
                cr.set_source_rgba(0.2, 0.5, 1.0, 0.8)
                cr.rectangle(0, 0, thresh_x, height)
                cr.fill()
                cr.set_source_rgba(1.0, 0.55, 0.1, 0.9)
                cr.rectangle(thresh_x, 0, fill_w - thresh_x, height)
                cr.fill()
        cr.set_source_rgba(1.0, 0.85, 0.0, 0.9)
        cr.set_line_width(1)
        cr.move_to(thresh_x, 0)
        cr.line_to(thresh_x, height)
        cr.stroke()

    def _redraw_canvases(self) -> bool:
        self._mic_canvas.queue_draw()
        return True

    def start_elapsed_timer(self) -> None:
        self._session_start = time.monotonic()
        self._elapsed_timer_id = GLib.timeout_add_seconds(1, self._tick_elapsed)
        self._redraw_timer_id = GLib.timeout_add(50, self._redraw_canvases)

    def stop_elapsed_timer(self) -> None:
        if self._elapsed_timer_id is not None:
            GLib.source_remove(self._elapsed_timer_id)
            self._elapsed_timer_id = None
        if self._redraw_timer_id is not None:
            GLib.source_remove(self._redraw_timer_id)
            self._redraw_timer_id = None

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
        self._analyze_button.set_sensitive(count > 0)

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

    def update_slack_status(
        self, connected: bool, workspace: str = "", channel: str = ""
    ) -> None:
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
