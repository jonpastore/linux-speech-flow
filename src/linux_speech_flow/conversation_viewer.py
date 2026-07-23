from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from linux_speech_flow.config import load_config


def _parse_conv_metadata(file_path: str) -> dict:
    """Read the first 6 lines of a conversation file to extract header metadata.
    Returns dict with keys: date, duration, chunks, models, title.
    title is derived from the filename (strip timestamp prefix and .txt suffix).
    """
    meta = {"date": "", "duration": "", "chunks": "", "models": "", "title": ""}
    try:
        fname = Path(file_path).stem  # e.g. "20260221T123456_my-topic"
        parts = fname.split("_", 1)
        meta["title"] = parts[1].replace("-", " ") if len(parts) > 1 else fname
        with open(file_path, encoding="utf-8", errors="replace") as f:
            for _ in range(6):
                line = f.readline()
                if line.startswith("Date:"):
                    meta["date"] = line.split(":", 1)[1].strip()
                elif line.startswith("Duration:"):
                    meta["duration"] = line.split(":", 1)[1].strip()
                elif line.startswith("Chunks:"):
                    meta["chunks"] = line.split(":", 1)[1].strip()
                elif line.startswith("Models:"):
                    meta["models"] = line.split(":", 1)[1].strip()
    except OSError:
        pass
    return meta


class ConversationViewer(Gtk.ApplicationWindow):
    """Two-panel conversation file browser.

    Left: list of conversations sorted by modification time (newest first).
    Right: full file content preview of selected conversation.
    """

    def __init__(self, application, on_continue_qa=None):
        """
        Args:
            on_continue_qa: Optional Callable(file_path: str) — called when
                user clicks "Continue Q&A" for a conversation file.
        """
        super().__init__(application=application, title="Conversation History")
        self._on_continue_qa = on_continue_qa
        config = load_config()
        w = config.get("conv_viewer_width", 900)
        h = config.get("conv_viewer_height", 600)
        self.set_default_size(w, h)
        self.set_resizable(True)

        paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        paned.set_position(280)
        self.set_child(paned)

        # Left: scrollable list
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_scroll.set_size_request(200, -1)
        paned.set_start_child(list_scroll)  # GTK4 API
        paned.set_resize_start_child(False)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect("row-activated", self._on_row_activated)
        list_scroll.set_child(self._listbox)

        # Right: preview
        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        paned.set_end_child(preview_scroll)  # GTK4 API
        paned.set_resize_end_child(True)

        self._preview = Gtk.TextView()
        self._preview.set_editable(False)
        self._preview.set_cursor_visible(False)
        self._preview.set_wrap_mode(Gtk.WrapMode.WORD)
        self._preview.set_left_margin(12)
        self._preview.set_right_margin(12)
        self._preview.set_top_margin(8)
        self._preview.set_bottom_margin(8)
        preview_scroll.set_child(self._preview)

        self._file_paths: list[str] = []
        self._load_conversations()

    def _load_conversations(self) -> None:
        """Scan conv_save_dir and populate list. Called on init and refresh."""
        config = load_config()
        save_dir = Path(
            config.get("conv_save_dir", "~/Documents/conversations")
        ).expanduser()

        while True:
            row = self._listbox.get_row_at_index(0)
            if row is None:
                break
            self._listbox.remove(row)
        self._file_paths = []

        if not save_dir.exists():
            placeholder = Gtk.Label(label="No conversations yet.\nStart one with F11.")
            placeholder.set_margin_start(16)
            placeholder.set_margin_top(16)
            placeholder.set_wrap(True)
            row = Gtk.ListBoxRow()
            row.set_child(placeholder)
            self._listbox.append(row)
            return

        files = sorted(
            save_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        self._file_paths = [str(p) for p in files]

        for file_path in self._file_paths:
            meta = _parse_conv_metadata(file_path)
            row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            row_box.set_margin_start(12)
            row_box.set_margin_end(8)
            row_box.set_margin_top(8)
            row_box.set_margin_bottom(4)

            title_label = Gtk.Label(label=meta["title"] or "(untitled)")
            title_label.add_css_class("body")
            title_label.set_xalign(0)
            title_label.set_ellipsize(3)  # Pango.EllipsizeMode.END = 3
            row_box.append(title_label)

            sub_parts = []
            if meta["date"]:
                sub_parts.append(meta["date"][:10])
            if meta["duration"]:
                sub_parts.append(meta["duration"])
            subtitle = Gtk.Label(label=" | ".join(sub_parts))
            subtitle.add_css_class("caption")
            subtitle.set_xalign(0)
            subtitle.set_opacity(0.7)
            row_box.append(subtitle)

            if self._on_continue_qa:
                qa_btn = Gtk.Button(label="Continue Q&A")
                qa_btn.add_css_class("flat")
                fp = file_path  # capture for closure
                qa_btn.connect("clicked", lambda _b, p=fp: self._on_continue_qa(p))
                row_box.append(qa_btn)

            row = Gtk.ListBoxRow()
            row.set_child(row_box)
            self._listbox.append(row)

        if not files:
            placeholder = Gtk.Label(label="No conversations yet.\nStart one with F11.")
            placeholder.set_margin_start(16)
            placeholder.set_margin_top(16)
            placeholder.set_wrap(True)
            row = Gtk.ListBoxRow()
            row.set_child(placeholder)
            self._listbox.append(row)

    def _on_row_activated(self, _listbox, row) -> None:
        """Load selected file content into preview pane."""
        idx = row.get_index()
        if idx < 0 or idx >= len(self._file_paths):
            return
        file_path = self._file_paths[idx]
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            content = f"(Could not read file: {exc})"
        buf = self._preview.get_buffer()
        buf.set_text(content)
