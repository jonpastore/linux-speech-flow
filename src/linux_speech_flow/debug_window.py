import logging

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk


class DebugWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Debug Log")
        self.set_default_size(720, 400)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(box)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)
        clear_btn = Gtk.Button(label="Clear")
        clear_btn.connect("clicked", self._on_clear)
        toolbar.append(clear_btn)
        box.append(toolbar)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.append(sep)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self._view = Gtk.TextView()
        self._view.set_editable(False)
        self._view.set_monospace(True)
        self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._view.set_margin_start(8)
        self._view.set_margin_end(8)
        self._view.set_margin_top(4)
        scroll.set_child(self._view)
        box.append(scroll)

        self._buf = self._view.get_buffer()
        self._end_mark = self._buf.create_mark("end", self._buf.get_end_iter(), False)

    def _on_clear(self, _btn):
        self._buf.set_text("")

    def append_log(self, text: str):
        GLib.idle_add(self._do_append, text)

    def _do_append(self, text: str):
        end = self._buf.get_end_iter()
        self._buf.insert(end, text + "\n")
        self._buf.move_mark(self._end_mark, self._buf.get_end_iter())
        self._view.scroll_to_mark(self._end_mark, 0.0, True, 0.0, 1.0)
        return False

    def as_log_handler(self) -> logging.Handler:
        return _DebugWindowHandler(self)


class _DebugWindowHandler(logging.Handler):
    def __init__(self, window: DebugWindow):
        super().__init__()
        self._window = window
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-5s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord):
        try:
            self._window.append_log(self.format(record))
        except Exception:
            self.handleError(record)
