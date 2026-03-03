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

    def __init__(self, application):
        super().__init__(application=application, title="Conversation Recording")
        self.set_default_size(360, 260)
        self.set_resizable(False)
        self.set_deletable(False)  # prevent window manager close during recording

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

        # Mic level bar with threshold marker overlay
        mic_overlay = Gtk.Overlay()
        self._mic_level_bar = Gtk.LevelBar()
        self._mic_level_bar.set_min_value(0.0)
        self._mic_level_bar.set_max_value(1.0)
        self._mic_level_bar.set_value(0.0)
        mic_overlay.set_child(self._mic_level_bar)

        self._threshold_area = Gtk.DrawingArea()
        self._threshold_area.set_can_target(False)
        self._threshold_area.set_draw_func(self._draw_threshold, None)
        mic_overlay.add_overlay(self._threshold_area)

        box.append(mic_overlay)

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

    def start(self) -> None:
        """Begin elapsed timer. Call when ConversationManager starts recording."""
        self._started_at = time.monotonic()
        self._timer_id = GLib.timeout_add_seconds(1, self._update_elapsed)
        self._update_elapsed()

    def stop(self) -> None:
        """Stop elapsed timer. Call when ConversationManager stops recording."""
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
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
        """Update mic level bar. level is RMS*scale clamped to 0.0–1.0. GTK main thread only."""
        self._mic_level_bar.set_value(level)

    def _draw_threshold(self, area, cr, width, height, _data) -> None:
        """Draw a vertical threshold marker line on the mic level bar overlay."""
        from linux_speech_flow.conversation_recorder import RMS_DISPLAY_SCALE
        normalized = min(1.0, self._silence_threshold * RMS_DISPLAY_SCALE)
        x = normalized * width
        cr.set_source_rgba(0, 0, 0, 0.6)
        cr.set_line_width(3)
        cr.move_to(x, 0)
        cr.line_to(x, height)
        cr.stroke()
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.set_line_width(2)
        cr.move_to(x, 0)
        cr.line_to(x, height)
        cr.stroke()

    def _update_elapsed(self) -> bool:
        if self._started_at is None:
            return False
        elapsed = int(time.monotonic() - self._started_at)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self._elapsed_label.set_text(f"{h}:{m:02d}:{s:02d}")
        return True  # keep GLib timer firing
