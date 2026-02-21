import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from linux_speech_flow.config import load_config


class ConversationDialog(Gtk.ApplicationWindow):
    def __init__(self, application, transcript: str, metadata: dict,
                 on_submit, on_cancel=None):
        super().__init__(application=application, title="Conversation Analysis")
        self.set_default_size(560, 680)
        self.set_resizable(True)
        self.set_modal(True)

        self._transcript = transcript
        self._metadata = metadata
        self.on_submit_cb = on_submit
        self._on_cancel = on_cancel

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

        if self._questions:
            questions_label = Gtk.Label(label="Qualifying Questions")
            questions_label.add_css_class("title-4")
            questions_label.set_xalign(0)
            questions_label.set_margin_top(8)
            content.append(questions_label)

        self._answer_entries = []
        for question in self._questions:
            q_label = Gtk.Label(label=question)
            q_label.set_xalign(0)
            q_label.set_wrap(True)
            q_label.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            content.append(q_label)

            answer_entry = Gtk.Entry()
            answer_entry.set_placeholder_text("Your answer...")
            content.append(answer_entry)
            self._answer_entries.append(answer_entry)

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

        self._save_check = Gtk.CheckButton(label="Save to file")
        self._save_check.set_active(True)
        content.append(self._save_check)

        self._inject_check = Gtk.CheckButton(label="Inject to active window")
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
        self._grok_check.set_active(False)
        if not grok_key:
            self._grok_check.set_sensitive(False)
            self._grok_check.set_tooltip_text("Add API key in Settings to enable")
        content.append(self._grok_check)

        gemini_key = config.get("gemini_api_key", "")
        self._gemini_check = Gtk.CheckButton(label="Gemini")
        self._gemini_check.set_active(False)
        if not gemini_key:
            self._gemini_check.set_sensitive(False)
            self._gemini_check.set_tooltip_text("Add API key in Settings to enable")
        content.append(self._gemini_check)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_start(24)
        btn_row.set_margin_end(24)
        btn_row.set_margin_top(8)
        btn_row.set_margin_bottom(16)
        outer.append(btn_row)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_row.append(spacer)

        submit_btn = Gtk.Button(label="Submit")
        submit_btn.add_css_class("suggested-action")
        submit_btn.connect("clicked", self._on_submit)
        btn_row.append(submit_btn)

    def _on_submit(self, _btn):
        prompt = self._prompt_buf.get_text(
            self._prompt_buf.get_start_iter(),
            self._prompt_buf.get_end_iter(), False)
        qualifying_answers = "\n".join(
            f"Q: {q}\nA: {e.get_text()}"
            for q, e in zip(self._questions, self._answer_entries)
        )
        selected_models = []
        if self._groq_check.get_active():
            selected_models.append('groq')
        if self._grok_check.get_active() and self._grok_check.get_sensitive():
            selected_models.append('grok')
        if self._gemini_check.get_active() and self._gemini_check.get_sensitive():
            selected_models.append('gemini')
        if not selected_models:
            selected_models = ['groq']
        self.on_submit_cb(
            self._transcript, prompt, qualifying_answers,
            selected_models,
            self._save_check.get_active(),
            self._inject_check.get_active(),
            self._metadata,
        )
        self.close()

    def _on_close_request(self, _window):
        if self._on_cancel:
            self._on_cancel()
        return False
