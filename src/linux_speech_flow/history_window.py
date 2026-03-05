import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Pango, GLib
from datetime import datetime
from pathlib import Path
from linux_speech_flow.config import load_config, save_config
from linux_speech_flow.history import HistoryStore


class HistoryRow(Gtk.ListBoxRow):
    def __init__(self, entry):
        super().__init__()
        self._expanded = False

        raw_text = entry["raw_text"] or ""
        processed_text = entry["processed_text"] or ""

        try:
            dt = datetime.fromisoformat(entry["created_at"])
            timestamp_str = dt.strftime("%b %d %H:%M")
        except (ValueError, TypeError):
            timestamp_str = str(entry["created_at"] or "")

        duration_str = f"{float(entry['duration_sec'] or 0):.1f}s"
        preview_text = (processed_text or raw_text)[:80]

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(outer)

        compact_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        compact_box.set_margin_start(12)
        compact_box.set_margin_end(12)
        compact_box.set_margin_top(8)
        compact_box.set_margin_bottom(8)
        outer.append(compact_box)

        timestamp_label = Gtk.Label(label=timestamp_str)
        timestamp_label.set_xalign(0.0)
        compact_box.append(timestamp_label)

        duration_label = Gtk.Label(label=duration_str)
        duration_label.add_css_class("dim-label")
        duration_label.set_width_chars(6)
        compact_box.append(duration_label)

        preview_label = Gtk.Label(label=preview_text)
        preview_label.set_hexpand(True)
        preview_label.set_xalign(0.0)
        preview_label.set_ellipsize(Pango.EllipsizeMode.END)
        compact_box.append(preview_label)

        self._detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._detail.set_margin_start(12)
        self._detail.set_margin_end(12)
        self._detail.set_margin_bottom(12)
        self._detail.set_visible(False)
        outer.append(self._detail)

        processed_header = Gtk.Label(label="Processed")
        processed_header.set_xalign(0.0)
        attrs = Pango.AttrList()
        attrs.insert(Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold")))
        processed_header.set_attributes(attrs)
        self._detail.append(processed_header)

        processed_label = Gtk.Label(label=processed_text)
        processed_label.set_xalign(0.0)
        processed_label.set_wrap(True)
        processed_label.set_selectable(True)
        self._detail.append(processed_label)

        copy_processed_btn = Gtk.Button(label="Copy")
        copy_processed_btn.connect(
            "clicked",
            lambda _btn, t=processed_text: Gdk.Display.get_default()
            .get_clipboard()
            .set(t),
        )
        self._detail.append(copy_processed_btn)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._detail.append(sep)

        raw_header = Gtk.Label(label="Raw transcript")
        raw_header.set_xalign(0.0)
        raw_header.add_css_class("dim-label")
        self._detail.append(raw_header)

        raw_bg_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        raw_bg_box.add_css_class("history-raw-bg")
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            b".history-raw-bg { background-color: alpha(@window_bg_color, 0.5); }"
        )
        raw_bg_box.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self._detail.append(raw_bg_box)

        raw_label = Gtk.Label(label=raw_text)
        raw_label.set_xalign(0.0)
        raw_label.set_wrap(True)
        raw_label.set_selectable(True)
        raw_bg_box.append(raw_label)

        copy_raw_btn = Gtk.Button(label="Copy")
        copy_raw_btn.connect(
            "clicked",
            lambda _btn, t=raw_text: Gdk.Display.get_default().get_clipboard().set(t),
        )
        self._detail.append(copy_raw_btn)

        app_name = entry["app_name"] or "—"
        window_title = entry["window_title"] or "—"
        context_label = Gtk.Label(label=f"App: {app_name}  |  Window: {window_title}")
        context_label.add_css_class("dim-label")
        context_label.set_xalign(0.0)
        self._detail.append(context_label)

    def toggle_expand(self):
        self._expanded = not self._expanded
        self._detail.set_visible(self._expanded)


class HistoryWindow(Gtk.ApplicationWindow):
    def __init__(self, application, history_store: HistoryStore):
        super().__init__(application=application, title="linux-speech-flow — History")
        self._history_store = history_store

        cfg = load_config()
        w = cfg.get("history_window_width", 700)
        h = cfg.get("history_window_height", 500)
        self.set_default_size(w, h)

        self.connect("close-request", self._on_close_request)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_box.set_margin_start(12)
        header_box.set_margin_end(12)
        header_box.set_margin_top(8)
        header_box.set_margin_bottom(8)
        root.append(header_box)

        title_label = Gtk.Label(label="Transcription History")
        title_label.set_xalign(0.0)
        title_label.set_hexpand(True)
        header_box.append(title_label)

        clear_all_btn = Gtk.Button(label="Clear All History")
        clear_all_btn.connect("clicked", self._on_clear_history)
        header_box.append(clear_all_btn)

        header_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(header_sep)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        root.append(scroll)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._listbox.set_activate_on_single_click(True)
        self._listbox.connect("row-activated", lambda lb, row: row.toggle_expand())
        scroll.set_child(self._listbox)

        footer_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(footer_sep)

        self._footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._footer.set_margin_start(8)
        self._footer.set_margin_end(8)
        self._footer.set_margin_top(8)
        self._footer.set_margin_bottom(8)
        root.append(self._footer)

        clear_temp_btn = Gtk.Button(label="Clear Temp Audio Files")
        clear_temp_btn.connect("clicked", self._on_clear_temp_audio)
        self._footer.append(clear_temp_btn)

        self._footer_status = Gtk.Label(label="")
        self._footer_status.set_xalign(0.0)
        self._footer_status.set_hexpand(True)
        self._footer.append(self._footer_status)

        self._load_rows()

    def _load_rows(self):
        child = self._listbox.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self._listbox.remove(child)
            child = next_child

        entries = self._history_store.fetch_all()
        if not entries:
            cfg = load_config()
            from linux_speech_flow.hotkey import combo_display

            hotkey_combo = cfg.get("hotkey_record", "ctrl+alt+r")
            empty_label = Gtk.Label(
                label=f"No transcriptions yet. Press {combo_display(hotkey_combo)} to start recording."
            )
            empty_label.set_margin_top(24)
            empty_label.set_margin_bottom(24)
            empty_label.set_xalign(0.5)
            self._listbox.append(empty_label)
        else:
            for entry in entries:
                self._listbox.append(HistoryRow(entry))

    def prepend_entry(self, entry: dict) -> bool:
        first = self._listbox.get_first_child()
        if first is not None and isinstance(first, Gtk.Label):
            self._listbox.remove(first)

        row = HistoryRow(entry)
        self._listbox.prepend(row)
        return False

    def _on_clear_history(self, _btn):
        dialog = Gtk.Window(title="Confirm Clear")
        dialog.set_modal(True)
        dialog.set_transient_for(self)
        dialog.set_default_size(340, 140)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        dialog.set_child(box)

        msg = Gtk.Label(label="Clear all transcription history? This cannot be undone.")
        msg.set_wrap(True)
        msg.set_xalign(0.0)
        box.append(msg)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _b: dialog.close())
        btn_row.append(cancel_btn)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.add_css_class("destructive-action")

        def _do_clear(_b):
            dialog.close()
            self._history_store.clear_all()
            self._load_rows()

        clear_btn.connect("clicked", _do_clear)
        btn_row.append(clear_btn)

        dialog.present()

    def _on_clear_temp_audio(self, _btn):
        failed_dir = Path.home() / ".local" / "share" / "linux-speech-flow" / "failed"
        count = 0
        if failed_dir.exists():
            for wav_file in failed_dir.glob("*.wav"):
                try:
                    wav_file.unlink()
                    count += 1
                except OSError:
                    pass
        self._footer_status.set_label(f"Temp audio files cleared ({count} removed).")

    def _on_close_request(self, _window) -> bool:
        w, h = self.get_default_size()
        cfg = load_config()
        cfg["history_window_width"] = w
        cfg["history_window_height"] = h
        save_config(cfg)
        return False
