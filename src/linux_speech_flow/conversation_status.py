import time
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib


class ConversationStatusWindow(Gtk.ApplicationWindow):
    """Live status display for an active conversation recording.

    Shows: elapsed timer, chunk count, last chunk status.
    Updated every second via GLib.timeout_add_seconds.
    Created/destroyed by ConversationManager; not user-closeable during recording.
    """

    def __init__(self, application):
        super().__init__(application=application, title="Conversation Recording")
        self.set_default_size(360, 200)
        self.set_resizable(False)
        self.set_deletable(False)  # prevent window manager close during recording

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

        self._transcript_label = Gtk.Label(label="")
        self._transcript_label.set_wrap(True)
        self._transcript_label.set_halign(Gtk.Align.START)
        self._transcript_label.set_max_width_chars(48)
        box.append(self._transcript_label)

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

    def _update_elapsed(self) -> bool:
        if self._started_at is None:
            return False
        elapsed = int(time.monotonic() - self._started_at)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self._elapsed_label.set_text(f"{h}:{m:02d}:{s:02d}")
        return True  # keep GLib timer firing
