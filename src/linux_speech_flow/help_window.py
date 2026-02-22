import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango


HOTKEYS = [
    ("F9", "Start / stop transcription"),
    ("ESC", "Cancel recording"),
    ("F10", "Reprocess last failed transcription"),
    ("F11", "Start / stop conversation mode"),
    ("F12", "Toggle conversation feedback (status window ↔ tray only)"),
]


class HelpWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Hotkeys")
        self.set_default_size(420, 260)
        self.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        self.set_child(box)

        title = Gtk.Label(label="Hotkeys")
        title.add_css_class("title-4")
        title.set_xalign(0)
        box.append(title)

        grid = Gtk.Grid()
        grid.set_column_spacing(24)
        grid.set_row_spacing(8)
        box.append(grid)

        bold_desc = Pango.FontDescription.from_string("bold")

        for row, (key, desc) in enumerate(HOTKEYS):
            key_label = Gtk.Label(label=key)
            key_label.set_xalign(1)
            key_label.set_valign(Gtk.Align.CENTER)
            attrs = Pango.AttrList()
            attrs.insert(Pango.AttrFontDesc.new(bold_desc))
            key_label.set_attributes(attrs)
            key_label.add_css_class("monospace")

            desc_label = Gtk.Label(label=desc)
            desc_label.set_xalign(0)
            desc_label.set_valign(Gtk.Align.CENTER)
            desc_label.set_wrap(True)

            grid.attach(key_label, 0, row, 1, 1)
            grid.attach(desc_label, 1, row, 1, 1)
