import math
import time
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from linux_speech_flow.config import load_config


class ConversationStatusWindow(Gtk.ApplicationWindow):
    """Live status display for an active conversation recording.

    Shows: elapsed timer, chunk count, silence drain bar, mic level bar.
    Updated every second via GLib.timeout_add_seconds; silence bar animates
    at 50ms via the mic redraw timer.
    Created/destroyed by ConversationManager; not user-closeable during recording.
    """

    def __init__(self, application, on_threshold_changed=None, on_stop_clicked=None):
        super().__init__(application=application, title="Conversation Recording")
        self.set_default_size(360, 320)
        self.set_resizable(False)
        self.set_deletable(False)
        self.set_focus_on_click(False)

        self._on_threshold_changed = on_threshold_changed
        self._on_stop_clicked = on_stop_clicked

        config = load_config()
        self._silence_threshold = config.get("conv_silence_rms_threshold", 0.005)

        # Silence drain bar state
        self._silence_started_at: float | None = None
        self._warn_sec: int = config.get("conv_silence_warn_sec", 30)
        self._stop_sec: int = config.get("conv_silence_stop_sec", 60)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        self.set_child(box)

        self._elapsed_label = Gtk.Label(label="0:00:00")
        self._elapsed_label.add_css_class("title-1")
        box.append(self._elapsed_label)

        self._status_label = Gtk.Label(label="Starting...")
        self._status_label.set_wrap(True)
        box.append(self._status_label)

        # Silence drain bar — red bar that empties as silence grows
        silence_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        silence_title = Gtk.Label(label="Silence")
        silence_title.set_halign(Gtk.Align.START)
        silence_title.add_css_class("caption")
        self._silence_time_label = Gtk.Label(label="")
        self._silence_time_label.set_halign(Gtk.Align.END)
        self._silence_time_label.set_hexpand(True)
        self._silence_time_label.add_css_class("caption")
        silence_header.append(silence_title)
        silence_header.append(self._silence_time_label)
        box.append(silence_header)

        self._silence_canvas = Gtk.DrawingArea()
        self._silence_canvas.set_hexpand(True)
        self._silence_canvas.set_size_request(-1, 20)
        self._silence_canvas.set_draw_func(self._draw_silence_bar, None)
        box.append(self._silence_canvas)

        # Mic level bar
        self._mic_level = 0.0
        self._mic_canvas = Gtk.DrawingArea()
        self._mic_canvas.set_hexpand(True)
        self._mic_canvas.set_size_request(-1, 16)
        self._mic_canvas.set_draw_func(self._draw_mic, None)
        box.append(self._mic_canvas)

        # Threshold slider
        thresh_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        thresh_label = Gtk.Label(label="Threshold:")
        thresh_label.set_halign(Gtk.Align.START)
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

        transcript_scroll = Gtk.ScrolledWindow()
        transcript_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        transcript_scroll.set_min_content_height(72)
        transcript_scroll.set_max_content_height(72)
        transcript_scroll.add_css_class("card")
        self._transcript_view = Gtk.TextView()
        self._transcript_view.set_editable(False)
        self._transcript_view.set_cursor_visible(False)
        self._transcript_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._transcript_view.set_margin_start(8)
        self._transcript_view.set_margin_end(8)
        self._transcript_view.set_margin_top(6)
        self._transcript_view.set_margin_bottom(6)
        self._transcript_buf = self._transcript_view.get_buffer()
        transcript_scroll.set_child(self._transcript_view)
        box.append(transcript_scroll)

        stop_btn = Gtk.Button(label="Stop Recording")
        stop_btn.add_css_class("destructive-action")
        stop_btn.connect("clicked", self._on_stop_btn_clicked)
        box.append(stop_btn)

        self._started_at = None
        self._timer_id = None
        self._redraw_timer_id = None

    def _on_stop_btn_clicked(self, _btn) -> None:
        if self._on_stop_clicked:
            self._on_stop_clicked(reason="status_window_stop")

    def start(self) -> None:
        self._started_at = time.monotonic()
        self._timer_id = GLib.timeout_add_seconds(1, self._update_elapsed)
        self._redraw_timer_id = GLib.timeout_add(50, self._redraw_canvases)
        self._update_elapsed()

    def stop(self) -> None:
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        if self._redraw_timer_id:
            GLib.source_remove(self._redraw_timer_id)
            self._redraw_timer_id = None
        self.set_deletable(True)

    def set_silence_baseline(
        self, started_at: float, warn_sec: int, stop_sec: int
    ) -> None:
        """Called by ConversationManager whenever silence timers reset (speech or chunk).
        started_at is time.monotonic() of the reset. Bar animates from full → empty
        over stop_sec seconds; dialog pops at warn_sec (bar halfway point).
        """
        self._silence_started_at = started_at
        self._warn_sec = warn_sec
        self._stop_sec = stop_sec

    def update_status(self, chunk_count: int, last_status: str) -> None:
        self._status_label.set_text(
            f"{chunk_count} chunk{'s' if chunk_count != 1 else ''} transcribed | {last_status}"
        )

    def set_threshold_from_calibration(self, value: float) -> None:
        """Update threshold slider to reflect auto-calibrated value."""
        self._silence_threshold = value
        self._thresh_slider.set_value(value)

    def update_silence(self, silence_seconds: int) -> None:
        pass  # superseded by animated bar; kept for API compatibility

    def clear_transcript(self) -> None:
        self._transcript_buf.set_text("")

    def update_transcript(self, text: str) -> None:
        end = self._transcript_buf.get_end_iter()
        sep = " " if self._transcript_buf.get_char_count() > 0 else ""
        self._transcript_buf.insert(end, sep + text)
        end = self._transcript_buf.get_end_iter()
        self._transcript_view.scroll_to_iter(end, 0.0, False, 0.0, 1.0)

    def update_mic_level(self, level: float) -> None:
        self._mic_level = level

    def _redraw_canvases(self) -> bool:
        self._mic_canvas.queue_draw()
        self._silence_canvas.queue_draw()
        return True

    def _on_thresh_slider(self, slider) -> None:
        value = slider.get_value()
        self._silence_threshold = value
        if self._on_threshold_changed:
            self._on_threshold_changed(value)

    def _draw_silence_bar(self, area, cr, width, height, _data) -> None:
        """Drain bar: full = no silence, empty = autostop. Green → red as silence grows."""
        if self._silence_started_at is None or self._stop_sec <= 0:
            # No baseline yet — draw full green bar
            cr.set_source_rgba(0.2, 0.75, 0.3, 0.6)
            cr.rectangle(0, 0, width, height)
            cr.fill()
            return

        elapsed = time.monotonic() - self._silence_started_at
        fraction = max(0.0, 1.0 - elapsed / self._stop_sec)
        warn_fraction = 1.0 - (self._warn_sec / self._stop_sec)

        # Background track
        cr.set_source_rgba(0.15, 0.15, 0.15, 0.5)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        fill_w = fraction * width
        if fill_w > 0:
            if fraction > warn_fraction:
                # Safe zone (before warn): green
                r, g, b = 0.2, 0.78, 0.3
            else:
                # Danger zone (warn → stop): orange → red
                t = fraction / warn_fraction if warn_fraction > 0 else 0.0
                r = 1.0
                g = 0.35 * t  # orange at warn, red at 0
                b = 0.0
            cr.set_source_rgba(r, g, b, 0.85)
            cr.rectangle(0, 0, fill_w, height)
            cr.fill()

        # Warn threshold marker (yellow tick where dialog will pop)
        warn_x = warn_fraction * width
        if 0 < warn_x < width:
            cr.set_source_rgba(1.0, 0.9, 0.0, 0.9)
            cr.set_line_width(2)
            cr.move_to(warn_x, 0)
            cr.line_to(warn_x, height)
            cr.stroke()

        # Time label inside bar
        elapsed_int = int(elapsed)
        remaining = max(0, self._stop_sec - elapsed_int)
        self._silence_time_label.set_text(
            f"{elapsed_int}s / warn {self._warn_sec}s / stop {self._stop_sec}s"
        )

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
        cr.set_source_rgba(0, 0, 0, 0.7)
        cr.set_line_width(3)
        cr.move_to(thresh_x, 0)
        cr.line_to(thresh_x, height)
        cr.stroke()
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.set_line_width(2)
        cr.move_to(thresh_x, 0)
        cr.line_to(thresh_x, height)
        cr.stroke()

    def _update_elapsed(self) -> bool:
        if self._started_at is None:
            return False
        elapsed = int(time.monotonic() - self._started_at)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self._elapsed_label.set_text(f"{h}:{m:02d}:{s:02d}")
        return True
