import time
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from linux_speech_flow.config import load_config


class ConversationStatusWindow(Gtk.ApplicationWindow):
    """Live status display for an active conversation recording.

    Shows: elapsed timer, chunk count, last chunk status.
    Updated every second via GLib.timeout_add_seconds.
    Created/destroyed by ConversationManager; not user-closeable during recording.
    """

    def __init__(self, application, on_threshold_changed=None):
        super().__init__(application=application, title="Conversation Recording")
        self.set_default_size(360, 300)
        self.set_resizable(False)
        self.set_deletable(False)  # prevent window manager close during recording
        self.set_focus_on_click(False)  # don't steal keyboard focus from active window

        self._on_threshold_changed = on_threshold_changed

        config = load_config()
        self._silence_threshold = config.get("conv_silence_rms_threshold", 0.005)

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

        self._silence_label = Gtk.Label(label="Silence: 0s")
        self._silence_label.set_halign(Gtk.Align.START)
        box.append(self._silence_label)

        # Mic level bar — single DrawingArea draws level fill + threshold marker
        self._mic_level = 0.0
        self._mic_canvas = Gtk.DrawingArea()
        self._mic_canvas.set_hexpand(True)
        self._mic_canvas.set_size_request(-1, 16)
        self._mic_canvas.set_draw_func(self._draw_mic, None)
        box.append(self._mic_canvas)

        # Threshold slider for live adjustment
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

        transcript_frame = Gtk.Frame()
        transcript_frame.add_css_class("card")
        transcript_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        transcript_inner.set_margin_start(10)
        transcript_inner.set_margin_end(10)
        transcript_inner.set_margin_top(8)
        transcript_inner.set_margin_bottom(8)
        transcript_frame.set_child(transcript_inner)

        self._transcript_label = Gtk.Label(label="")
        self._transcript_label.set_wrap(True)
        self._transcript_label.set_halign(Gtk.Align.START)
        self._transcript_label.set_max_width_chars(48)
        self._transcript_label.add_css_class("body")
        transcript_inner.append(self._transcript_label)

        box.append(transcript_frame)

        self._started_at = None
        self._timer_id = None
        self._mic_redraw_timer_id = None

    def start(self) -> None:
        """Begin elapsed timer and mic redraw loop."""
        self._started_at = time.monotonic()
        self._timer_id = GLib.timeout_add_seconds(1, self._update_elapsed)
        self._mic_redraw_timer_id = GLib.timeout_add(50, self._redraw_mic)
        self._update_elapsed()

    def stop(self) -> None:
        """Stop timers. Call when ConversationManager stops recording."""
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        if self._mic_redraw_timer_id:
            GLib.source_remove(self._mic_redraw_timer_id)
            self._mic_redraw_timer_id = None
        self.set_deletable(True)

    def update_status(self, chunk_count: int, last_status: str) -> None:
        """Update status line. Call from GTK main thread."""
        self._status_label.set_text(
            f"{chunk_count} chunk{'s' if chunk_count != 1 else ''} transcribed | {last_status}"
        )

    def update_silence(self, silence_seconds: int) -> None:
        """Update silence timer display. Call from GTK main thread only."""
        self._silence_label.set_text(f"Silence: {silence_seconds}s")

    def update_transcript(self, text: str) -> None:
        """Display last chunk transcript text. Call from GTK main thread only."""
        self._transcript_label.set_text(text)

    def update_mic_level(self, level: float) -> None:
        """Update mic level value. Repaint driven by periodic timer."""
        self._mic_level = level

    def _redraw_mic(self) -> bool:
        """Periodic 50ms timer: force mic canvas repaint."""
        self._mic_canvas.queue_draw()
        return True  # keep timer firing

    def _on_thresh_slider(self, slider) -> None:
        value = slider.get_value()
        self._silence_threshold = value
        if self._on_threshold_changed:
            self._on_threshold_changed(value)

    def _draw_mic(self, area, cr, width, height, _data) -> None:
        """Draw mic level fill and threshold marker on the canvas."""
        from linux_speech_flow.conversation_recorder import RMS_DISPLAY_SCALE
        # Background track
        cr.set_source_rgba(0.2, 0.2, 0.2, 0.4)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        # Level fill: blue below threshold, orange above
        thresh_x = min(1.0, self._silence_threshold * RMS_DISPLAY_SCALE) * width
        fill_w = self._mic_level * width
        if fill_w > 0:
            if fill_w <= thresh_x:
                cr.set_source_rgba(0.2, 0.5, 1.0, 0.8)
            else:
                cr.set_source_rgba(0.2, 0.5, 1.0, 0.8)
                cr.rectangle(0, 0, thresh_x, height)
                cr.fill()
                cr.set_source_rgba(1.0, 0.55, 0.1, 0.9)
                cr.rectangle(thresh_x, 0, fill_w - thresh_x, height)
                cr.fill()
            if fill_w <= thresh_x:
                cr.rectangle(0, 0, fill_w, height)
                cr.fill()
        # Threshold marker line
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
        return True  # keep GLib timer firing
