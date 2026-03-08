import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Pango

from linux_speech_flow.config import load_config


def build_combined(
    transcript: str,
    summary: str = "",
    qa_rounds: list | None = None,
    action_items: list | None = None,
    confidence: float = 0.0,
    prompt: str = "",
) -> str:
    """Build a single text blob from all conversation components."""
    parts = []
    if summary:
        parts.append("## Summary\n\n" + summary)
    if action_items:
        parts.append("## Action Items\n\n" + "\n".join(f"- {a}" for a in action_items))
    if confidence > 0:
        parts.append(f"Confidence: {int(confidence * 100)}%")
    if qa_rounds:
        qa_text = "## Q&A\n\n"
        for r in qa_rounds:
            qa_text += f"**AI:** {r['question']}\n**You:** {r['answer']}\n\n"
        parts.append(qa_text.rstrip())
    parts.append("## Transcript\n\n" + transcript)
    if prompt:
        parts.append("## Analysis Prompt\n\n" + prompt)
    return "\n\n---\n\n".join(parts)


def _window_label(window_info: dict) -> str:
    """Return a short human-readable label for the target window."""
    title = window_info.get("title", "")
    wm_class = window_info.get("wm_class", "")
    return title or wm_class or "unknown"


def _do_transcript_copy(transcript: str) -> str:
    from linux_speech_flow.injector import copy_to_clipboard
    copy_to_clipboard(transcript)
    return "Copied to clipboard."


def _do_transcript_paste(transcript: str, window_info: dict) -> str:
    from linux_speech_flow.injector import paste_text
    paste_text(transcript, window_info)
    return "Pasted to active window."


def _do_transcript_save(transcript: str, metadata: dict) -> str:
    try:
        from pathlib import Path
        from linux_speech_flow.conversation_pipeline import conv_filename, coalesce_file

        config = load_config()
        save_dir = Path(
            config.get("conv_save_dir", "~/Documents/conversations")
        ).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)
        path = str(save_dir / conv_filename("transcript"))
        coalesce_file(path, metadata, "", [], transcript)
        return f"Saved: {path}"
    except Exception as exc:
        return f"Save failed: {exc}"


class ConversationDialog(Gtk.ApplicationWindow):
    def __init__(
        self,
        application,
        transcript: str,
        metadata: dict,
        on_submit,
        on_cancel=None,
        window_info: dict | None = None,
    ):
        super().__init__(application=application, title="Conversation Analysis")
        self.set_default_size(560, 720)
        self.set_resizable(True)
        self.set_modal(True)

        self._transcript = transcript
        self._metadata = metadata
        self.on_submit_cb = on_submit
        self._on_cancel = on_cancel
        self._window_info = window_info or {}

        config = load_config()
        self._questions = list(config.get("conv_qualifying_questions", []))

        self.connect("close-request", self._on_close_request)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer.append(scroll)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(24)
        content.set_margin_bottom(12)
        scroll.set_child(content)

        header = Gtk.Label(label="Conversation Analysis")
        header.add_css_class("title-3")
        header.set_xalign(0)
        content.append(header)

        # Transcript preview — always visible so user can see what they're working with
        transcript_label = Gtk.Label(label="Transcript")
        transcript_label.add_css_class("title-4")
        transcript_label.set_xalign(0)
        transcript_label.set_margin_top(8)
        content.append(transcript_label)

        transcript_scroll = Gtk.ScrolledWindow()
        transcript_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        transcript_scroll.set_min_content_height(100)
        transcript_scroll.set_max_content_height(180)
        transcript_view = Gtk.TextView()
        transcript_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        transcript_view.set_editable(False)
        transcript_view.set_cursor_visible(False)
        transcript_view.get_buffer().set_text(
            transcript or "(no transcript — chunks may still be transcribing)"
        )
        transcript_scroll.set_child(transcript_view)
        content.append(transcript_scroll)

        if self._questions:
            questions_label = Gtk.Label(label="Qualifying Questions")
            questions_label.add_css_class("title-4")
            questions_label.set_xalign(0)
            questions_label.set_margin_top(8)
            content.append(questions_label)

        self._answer_rows = []  # list of (CheckButton, Entry)
        for question in self._questions:
            q_check = Gtk.CheckButton(label=question)
            q_check.set_active(True)
            content.append(q_check)

            answer_entry = Gtk.Entry()
            answer_entry.set_placeholder_text("Your answer...")
            answer_entry.set_margin_start(24)
            q_check.connect(
                "toggled", lambda cb, e=answer_entry: e.set_sensitive(cb.get_active())
            )
            content.append(answer_entry)
            self._answer_rows.append((q_check, answer_entry))

        sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep1.set_margin_top(4)
        sep1.set_margin_bottom(4)
        content.append(sep1)

        prompt_label = Gtk.Label(label="Analysis Prompt")
        prompt_label.add_css_class("title-4")
        prompt_label.set_xalign(0)
        content.append(prompt_label)

        prompt_scroll = Gtk.ScrolledWindow()
        prompt_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        prompt_scroll.set_min_content_height(120)
        self._prompt_view = Gtk.TextView()
        self._prompt_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._prompt_buf = self._prompt_view.get_buffer()
        self._prompt_buf.set_text(config.get("conv_default_prompt", ""))
        prompt_scroll.set_child(self._prompt_view)
        content.append(prompt_scroll)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(4)
        sep2.set_margin_bottom(4)
        content.append(sep2)

        transcript_label = Gtk.Label(label="Transcript Output (immediate, raw text)")
        transcript_label.add_css_class("title-4")
        transcript_label.set_xalign(0)
        transcript_label.set_margin_top(4)
        content.append(transcript_label)

        self._copy_check = Gtk.CheckButton(label="Copy transcript to clipboard")
        self._copy_check.set_active(True)
        content.append(self._copy_check)

        can_paste = bool(self._window_info.get("window_id"))
        self._paste_check = Gtk.CheckButton(label="Paste transcript to active window")
        self._paste_check.set_active(False)
        self._paste_check.set_sensitive(can_paste)
        if not can_paste:
            self._paste_check.set_tooltip_text("Window ID not captured (X11 only)")
        content.append(self._paste_check)

        target_label = Gtk.Label(
            label=f"Target: {_window_label(self._window_info)}"
            if can_paste
            else "Target: (none captured)"
        )
        target_label.add_css_class("caption")
        target_label.set_xalign(0)
        target_label.set_margin_start(24)
        content.append(target_label)

        sep_transcript = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep_transcript.set_margin_top(4)
        sep_transcript.set_margin_bottom(4)
        content.append(sep_transcript)

        ai_label = Gtk.Label(label="AI Analysis Output")
        ai_label.add_css_class("title-4")
        ai_label.set_xalign(0)
        content.append(ai_label)

        self._save_check = Gtk.CheckButton(label="Save analysis to file")
        self._save_check.set_active(True)
        content.append(self._save_check)

        self._inject_check = Gtk.CheckButton(label="Inject analysis to active window")
        self._inject_check.set_active(False)
        content.append(self._inject_check)

        sep3 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep3.set_margin_top(4)
        sep3.set_margin_bottom(4)
        content.append(sep3)

        models_label = Gtk.Label(label="AI Models")
        models_label.add_css_class("title-4")
        models_label.set_xalign(0)
        content.append(models_label)

        groq_key = config.get("groq_api_key", "")
        self._groq_check = Gtk.CheckButton(label="Groq")
        self._groq_check.set_active(bool(groq_key))
        if not groq_key:
            self._groq_check.set_sensitive(False)
            self._groq_check.set_tooltip_text("Add API key in Settings to enable")
        content.append(self._groq_check)

        grok_key = config.get("grok_api_key", "")
        self._grok_check = Gtk.CheckButton(label="Grok")
        self._grok_check.set_active(bool(grok_key))
        if not grok_key:
            self._grok_check.set_sensitive(False)
            self._grok_check.set_tooltip_text("Add API key in Settings to enable")
        content.append(self._grok_check)

        gemini_key = config.get("gemini_api_key", "")
        self._gemini_check = Gtk.CheckButton(label="Gemini")
        self._gemini_check.set_active(bool(gemini_key))
        if not gemini_key:
            self._gemini_check.set_sensitive(False)
            self._gemini_check.set_tooltip_text("Add API key in Settings to enable")
        content.append(self._gemini_check)

        coalesce_label = Gtk.Label(label="Coalescing model (when multiple selected):")
        coalesce_label.add_css_class("caption")
        coalesce_label.set_xalign(0)
        coalesce_label.set_margin_top(4)
        content.append(coalesce_label)

        self._coalesce_combo = Gtk.ComboBoxText()
        self._coalesce_combo.append("groq", "Groq")
        self._coalesce_combo.append("grok", "Grok")
        self._coalesce_combo.append("gemini", "Gemini")
        self._coalesce_combo.set_active_id(config.get("conv_meta_model", "groq"))
        content.append(self._coalesce_combo)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_start(24)
        btn_row.set_margin_end(24)
        btn_row.set_margin_top(8)
        btn_row.set_margin_bottom(16)
        outer.append(btn_row)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_row.append(spacer)

        skip_btn = Gtk.Button(label="Skip Analysis")
        skip_btn.set_tooltip_text("Save/copy transcript without running AI analysis")
        skip_btn.connect("clicked", self._on_skip)
        btn_row.append(skip_btn)

        submit_btn = Gtk.Button(label="Analyse")
        submit_btn.add_css_class("suggested-action")
        submit_btn.connect("clicked", self._on_submit)
        btn_row.append(submit_btn)

    def _on_skip(self, _btn):
        """Close analysis dialog and open the transcript-only output window."""
        transcript = self._transcript
        metadata = self._metadata
        window_info = self._window_info
        app = self.get_application()
        self.close()
        win = TranscriptOutputWindow(
            application=app,
            transcript=transcript,
            metadata=metadata,
            window_info=window_info,
        )
        win.present()

    def _on_submit(self, _btn):
        prompt = self._prompt_buf.get_text(
            self._prompt_buf.get_start_iter(), self._prompt_buf.get_end_iter(), False
        )
        qualifying_answers = "\n".join(
            f"Q: {q}\nA: {e.get_text()}"
            for q, (cb, e) in zip(self._questions, self._answer_rows)
            if cb.get_active()
        )
        selected_models = []
        if self._groq_check.get_active():
            selected_models.append("groq")
        if self._grok_check.get_active() and self._grok_check.get_sensitive():
            selected_models.append("grok")
        if self._gemini_check.get_active() and self._gemini_check.get_sensitive():
            selected_models.append("gemini")
        if not selected_models:
            selected_models = ["groq"]
        meta_model = self._coalesce_combo.get_active_id() or "groq"
        from linux_speech_flow.config import save_config
        cfg = load_config()
        cfg["conv_meta_model"] = meta_model
        save_config(cfg)
        self.on_submit_cb(
            self._transcript,
            prompt,
            qualifying_answers,
            selected_models,
            self._save_check.get_active(),
            self._inject_check.get_active(),
            self._metadata,
            copy_to_clipboard=self._copy_check.get_active(),
            paste_to_window=self._paste_check.get_active(),
            window_info=self._window_info,
        )
        self.close()

    def _on_close_request(self, _window):
        if self._on_cancel:
            self._on_cancel()
        return False


class TranscriptOutputWindow(Gtk.ApplicationWindow):
    """Shown after 'Skip Analysis' or QA finalise — copy/paste/save the output."""

    def __init__(
        self,
        application,
        transcript: str,
        metadata: dict,
        window_info: dict | None = None,
        heading: str = "Raw Transcript",
        summary: str = "",
        qa_rounds: list | None = None,
        action_items: list | None = None,
        confidence: float = 0.0,
        prompt: str = "",
    ):
        title = "Analysis Output" if heading != "Raw Transcript" else "Transcript Output"
        super().__init__(application=application, title=title)
        self.set_default_size(520, 480)
        self.set_resizable(True)
        self.set_modal(True)

        self._transcript = transcript
        self._metadata = metadata
        self._window_info = window_info or {}
        self._summary = summary
        self._qa_rounds = qa_rounds or []
        self._action_items = action_items or []
        self._confidence = confidence
        self._prompt = prompt
        self._has_analysis = bool(summary)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_margin_top(16)
        content.set_margin_bottom(8)
        outer.append(content)

        header = Gtk.Label(label=heading)
        header.add_css_class("title-3")
        header.set_xalign(0)
        content.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        display_text = build_combined(
            self._transcript, summary, self._qa_rounds, self._action_items,
            self._confidence, self._prompt,
        )
        text_view.get_buffer().set_text(
            display_text or "(empty — session may not have produced transcribed chunks)"
        )
        scroll.set_child(text_view)
        content.append(scroll)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_xalign(0)
        self._status_label.add_css_class("caption")
        content.append(self._status_label)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        btn_box.set_margin_start(20)
        btn_box.set_margin_end(20)
        btn_box.set_margin_top(4)
        btn_box.set_margin_bottom(16)
        outer.append(btn_box)

        copy_btn = Gtk.Button(label="Copy All to Clipboard")
        copy_btn.add_css_class("suggested-action")
        copy_btn.set_tooltip_text("Copy full output (transcript + analysis + Q&A) to clipboard")
        copy_btn.connect("clicked", lambda _: self._do_copy())
        btn_box.append(copy_btn)

        can_paste = bool(self._window_info.get("window_id"))
        paste_label = (
            f"Paste to {_window_label(self._window_info)}"
            if can_paste
            else "Paste to Active Window"
        )
        paste_btn = Gtk.Button(label=paste_label)
        paste_btn.set_sensitive(can_paste)
        if not can_paste:
            paste_btn.set_tooltip_text("No active window captured (X11 only)")
        paste_btn.connect("clicked", lambda _: self._do_paste())
        btn_box.append(paste_btn)

        save_btn = Gtk.Button(label="Save Full Output to File...")
        save_btn.set_tooltip_text("Save transcript + analysis + Q&A as one structured file")
        save_btn.connect("clicked", lambda _: self._do_save("full"))
        btn_box.append(save_btn)

        if self._has_analysis:
            save_transcript_btn = Gtk.Button(label="Save Transcript Only...")
            save_transcript_btn.connect("clicked", lambda _: self._do_save("transcript"))
            btn_box.append(save_transcript_btn)

            save_analysis_btn = Gtk.Button(label="Save Analysis Only...")
            save_analysis_btn.set_tooltip_text("Save summary + action items + Q&A (no raw transcript)")
            save_analysis_btn.connect("clicked", lambda _: self._do_save("analysis"))
            btn_box.append(save_analysis_btn)

        done_btn = Gtk.Button(label="Done")
        done_btn.connect("clicked", lambda _: self.close())
        btn_box.append(done_btn)

    def _build_combined(self) -> str:
        return build_combined(
            self._transcript, self._summary, self._qa_rounds,
            self._action_items, self._confidence, self._prompt,
        )

    def _do_copy(self) -> None:
        from linux_speech_flow.injector import copy_to_clipboard
        copy_to_clipboard(self._build_combined())
        self._status_label.set_text("Copied to clipboard.")

    def _do_paste(self) -> None:
        from linux_speech_flow.injector import paste_text
        paste_text(self._build_combined(), self._window_info)
        self._status_label.set_text("Pasted to active window.")

    def _do_save(self, mode: str = "full") -> None:
        from pathlib import Path
        from linux_speech_flow.conversation_pipeline import conv_filename

        config = load_config()
        save_dir = Path(
            config.get("conv_save_dir", "~/Documents/conversations")
        ).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)

        label_map = {"full": "Save Output", "transcript": "Save Transcript", "analysis": "Save Analysis"}
        name_map = {"full": "output", "transcript": "transcript", "analysis": "analysis"}

        chooser = Gtk.FileChooserNative.new(
            label_map.get(mode, "Save"), self, Gtk.FileChooserAction.SAVE, "Save", "Cancel"
        )
        chooser.set_current_name(conv_filename(name_map.get(mode, "output")))
        try:
            from gi.repository import Gio
            chooser.set_current_folder(Gio.File.new_for_path(str(save_dir)))
        except Exception:
            pass
        chooser.connect("response", lambda c, r: self._on_save_response(c, r, mode))
        chooser.show()
        self._save_chooser = chooser

    def _on_save_response(self, chooser, response, mode: str) -> None:
        self._save_chooser = None
        if response != Gtk.ResponseType.ACCEPT:
            return
        gfile = chooser.get_file()
        if not gfile:
            return
        path = gfile.get_path()
        try:
            from linux_speech_flow.conversation_pipeline import coalesce_file

            if mode == "transcript":
                coalesce_file(path, self._metadata, "", [], self._transcript)
            elif mode == "analysis":
                coalesce_file(
                    path, self._metadata, self._summary, self._qa_rounds, "",
                    confidence=self._confidence, action_items=self._action_items,
                    prompt=self._prompt,
                )
            else:
                coalesce_file(
                    path, self._metadata, self._summary, self._qa_rounds, self._transcript,
                    confidence=self._confidence, action_items=self._action_items,
                    prompt=self._prompt,
                )
            self._status_label.set_text(f"Saved: {path}")
        except Exception as exc:
            self._status_label.set_text(f"Save failed: {exc}")
