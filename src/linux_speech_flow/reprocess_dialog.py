import subprocess

import gi

gi.require_version("Gtk", "4.0")
from pathlib import Path

from gi.repository import Gtk


class ReprocessDialog(Gtk.Window):
    """Modal window listing failed WAV recordings for reprocess selection."""

    def __init__(
        self, failed_wavs: list[str], on_selected, application=None, parent=None
    ):
        super().__init__(title="Reprocess Recordings", application=application)
        self.set_modal(True)
        self.set_default_size(500, 320)
        if parent:
            self.set_transient_for(parent)

        self._on_selected = on_selected
        self._rows: list[dict] = []

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer.append(scroll)

        self._list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._list_box.set_margin_start(16)
        self._list_box.set_margin_end(16)
        self._list_box.set_margin_top(16)
        self._list_box.set_margin_bottom(8)
        scroll.set_child(self._list_box)

        header = Gtk.Label(label="Select recordings to reprocess:")
        header.set_xalign(0)
        header.add_css_class("title-4")
        self._list_box.append(header)

        for wav_path in failed_wavs:
            self._add_row(wav_path)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_start(16)
        btn_row.set_margin_end(16)
        btn_row.set_margin_top(8)
        btn_row.set_margin_bottom(16)
        outer.append(btn_row)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_row.append(spacer)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _b: self.close())
        btn_row.append(cancel_btn)

        selected_btn = Gtk.Button(label="Reprocess Selected")
        selected_btn.add_css_class("suggested-action")
        selected_btn.connect("clicked", self._on_reprocess_selected)
        btn_row.append(selected_btn)

        all_btn = Gtk.Button(label="Reprocess All")
        all_btn.connect("clicked", self._on_reprocess_all)
        btn_row.append(all_btn)

    def _add_row(self, wav_path: str):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        check = Gtk.CheckButton()
        check.set_active(True)
        row.append(check)

        label = Gtk.Label(label=Path(wav_path).name)
        label.set_xalign(0)
        label.set_hexpand(True)
        label.set_ellipsize(3)
        row.append(label)

        play_btn = Gtk.Button(label="▶")
        play_btn.set_tooltip_text("Play recording")
        play_btn.connect("clicked", self._on_play, wav_path)
        row.append(play_btn)

        delete_btn = Gtk.Button(label="Delete")
        delete_btn.connect("clicked", self._on_delete, wav_path, row)
        row.append(delete_btn)

        self._list_box.append(row)
        self._rows.append(
            {"check": check, "path": wav_path, "row": row, "deleted": False}
        )

    def _on_play(self, _btn, wav_path: str):
        subprocess.Popen(["paplay", wav_path], stderr=subprocess.DEVNULL)

    def _on_delete(self, _btn, wav_path: str, row: Gtk.Box):
        try:
            Path(wav_path).unlink(missing_ok=True)
        except OSError:
            pass
        for entry in self._rows:
            if entry["path"] == wav_path:
                entry["deleted"] = True
                break
        self._list_box.remove(row)

    def _on_reprocess_selected(self, _btn):
        selected = [
            e["path"]
            for e in self._rows
            if not e["deleted"] and e["check"].get_active()
        ]
        if not selected:
            return
        self.close()
        self._on_selected(selected, "paste")

    def _on_reprocess_all(self, _btn):
        mode_win = _ModeSelectWindow(
            on_mode_selected=self._on_mode_chosen,
            parent=self,
            application=self.get_application(),
        )
        mode_win.present()

    def _on_mode_chosen(self, mode: str):
        remaining = [e["path"] for e in self._rows if not e["deleted"]]
        self.close()
        self._on_selected(remaining, mode)


class _ModeSelectWindow(Gtk.Window):
    """Small modal window asking user to choose batch reprocess mode."""

    def __init__(self, on_mode_selected, parent=None, application=None):
        super().__init__(title="Choose Reprocess Mode", application=application)
        self.set_modal(True)
        self.set_default_size(320, 160)
        if parent:
            self.set_transient_for(parent)

        self._on_mode_selected = on_mode_selected

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        self.set_child(box)

        label = Gtk.Label(label="How should reprocessed text be delivered?")
        label.set_wrap(True)
        label.set_xalign(0)
        box.append(label)

        paste_btn = Gtk.Button(label="Paste each into current window")
        paste_btn.add_css_class("suggested-action")
        paste_btn.connect("clicked", lambda _b: self._choose("paste"))
        box.append(paste_btn)

        file_btn = Gtk.Button(label="Write all to file")
        file_btn.connect("clicked", lambda _b: self._choose("file"))
        box.append(file_btn)

    def _choose(self, mode: str):
        self.close()
        self._on_mode_selected(mode)
