import math
import struct
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from linux_speech_flow.hotkey import (
    DANGEROUS_COMBOS,
    HOTKEY_ACTION_LABELS,
    HOTKEY_CONFIG_KEYS,
    HOTKEY_DEFAULTS,
    combo_display,
)

_GTK_MODIFIER_KEYSYMS: frozenset

LLM_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

import pulsectl

from linux_speech_flow.audio import list_microphones
from linux_speech_flow.config import load_config, save_config
from linux_speech_flow.groq_client import validate_api_key
from linux_speech_flow.history import HistoryStore
from linux_speech_flow.transcription import FAILED_DIR


def _block_scroll(combo: Gtk.ComboBoxText) -> None:
    ctrl = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
    ctrl.connect("scroll", lambda _c, _dx, _dy: True)
    combo.add_controller(ctrl)


def _block_scroll_spin(spin: Gtk.SpinButton) -> None:
    ctrl = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
    ctrl.connect("scroll", lambda _c, _dx, _dy: True)
    spin.add_controller(ctrl)


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, application, hotkey_manager=None):
        super().__init__(application=application, title="Settings")
        self._hotkey_manager = hotkey_manager
        self.set_default_size(480, 700)
        self.set_resizable(True)

        _css = Gtk.CssProvider()
        _css.load_from_data(b".success { color: @success_color; }")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            _css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self._mics = []
        self._config = load_config()
        self._closing = False
        self.connect("close-request", self._on_close)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        notebook = Gtk.Notebook()
        notebook.set_vexpand(True)
        outer.append(notebook)

        def _make_tab(label_text):
            _scroll = Gtk.ScrolledWindow()
            _scroll.set_vexpand(True)
            _scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            _box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            _box.set_margin_start(24)
            _box.set_margin_end(24)
            _box.set_margin_top(16)
            _box.set_margin_bottom(12)
            _scroll.set_child(_box)
            notebook.append_page(_scroll, Gtk.Label(label=label_text))
            return _box

        ai_tab = _make_tab("AI")
        content = ai_tab

        api_title = Gtk.Label(label="AI Integrations")
        api_title.add_css_class("title-4")
        api_title.set_xalign(0)
        content.append(api_title)

        provider_sub = Gtk.Label(label="Provider Mode")
        provider_sub.set_xalign(0)
        _attrs_p = Pango.AttrList()
        _attrs_p.insert(
            Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold"))
        )
        provider_sub.set_attributes(_attrs_p)
        content.append(provider_sub)

        self._provider_cloud_radio = Gtk.CheckButton(
            label="Cloud APIs (Groq/Grok/Gemini)"
        )
        self._provider_litellm_radio = Gtk.CheckButton(
            label="Local LiteLLM endpoint (free, self-hosted)"
        )
        self._provider_litellm_radio.set_group(self._provider_cloud_radio)
        if self._config.get("provider_mode", "cloud") == "litellm":
            self._provider_litellm_radio.set_active(True)
        else:
            self._provider_cloud_radio.set_active(True)
        content.append(self._provider_cloud_radio)
        content.append(self._provider_litellm_radio)

        groq_sub = Gtk.Label(label="Groq")
        groq_sub.set_xalign(0)
        _attrs = Pango.AttrList()
        _attrs.insert(Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold")))
        groq_sub.set_attributes(_attrs)
        content.append(groq_sub)

        self._api_key_entry = Gtk.PasswordEntry()
        self._api_key_entry.set_show_peek_icon(True)
        self._api_key_entry.set_property("placeholder-text", "gsk_...")
        if self._config.get("groq_api_key"):
            self._api_key_entry.set_text(self._config["groq_api_key"])
        content.append(self._api_key_entry)

        groq_test_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._validate_btn = Gtk.Button(label="Test")
        self._validate_btn.connect("clicked", self._on_validate)
        groq_test_row.append(self._validate_btn)
        self._groq_spinner = Gtk.Spinner()
        groq_test_row.append(self._groq_spinner)
        content.append(groq_test_row)

        self._groq_status = Gtk.Label(label="")
        self._groq_status.set_xalign(0)
        self._groq_status.set_wrap(True)
        self._groq_status.add_css_class("error")
        content.append(self._groq_status)

        grok_sub = Gtk.Label(label="Grok (xAI)")
        grok_sub.set_xalign(0)
        grok_sub.set_margin_top(8)
        _attrs2 = Pango.AttrList()
        _attrs2.insert(
            Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold"))
        )
        grok_sub.set_attributes(_attrs2)
        content.append(grok_sub)

        self._grok_key_entry = Gtk.PasswordEntry()
        self._grok_key_entry.set_show_peek_icon(True)
        self._grok_key_entry.set_property("placeholder-text", "xai-...")
        if self._config.get("grok_api_key"):
            self._grok_key_entry.set_text(self._config["grok_api_key"])
        content.append(self._grok_key_entry)

        grok_test_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._grok_test_btn = Gtk.Button(label="Test")
        self._grok_test_btn.connect("clicked", self._on_test_grok)
        grok_test_row.append(self._grok_test_btn)
        self._grok_spinner = Gtk.Spinner()
        grok_test_row.append(self._grok_spinner)
        content.append(grok_test_row)

        self._grok_status = Gtk.Label(label="")
        self._grok_status.set_xalign(0)
        self._grok_status.set_wrap(True)
        self._grok_status.add_css_class("error")
        content.append(self._grok_status)

        gemini_sub = Gtk.Label(label="Gemini (Google)")
        gemini_sub.set_xalign(0)
        gemini_sub.set_margin_top(8)
        _attrs3 = Pango.AttrList()
        _attrs3.insert(
            Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold"))
        )
        gemini_sub.set_attributes(_attrs3)
        content.append(gemini_sub)

        self._gemini_key_entry = Gtk.PasswordEntry()
        self._gemini_key_entry.set_show_peek_icon(True)
        self._gemini_key_entry.set_property("placeholder-text", "AIza...")
        if self._config.get("gemini_api_key"):
            self._gemini_key_entry.set_text(self._config["gemini_api_key"])
        content.append(self._gemini_key_entry)

        gemini_test_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._gemini_test_btn = Gtk.Button(label="Test")
        self._gemini_test_btn.connect("clicked", self._on_test_gemini)
        gemini_test_row.append(self._gemini_test_btn)
        self._gemini_spinner = Gtk.Spinner()
        gemini_test_row.append(self._gemini_spinner)
        content.append(gemini_test_row)

        self._gemini_status = Gtk.Label(label="")
        self._gemini_status.set_xalign(0)
        self._gemini_status.set_wrap(True)
        self._gemini_status.add_css_class("error")
        content.append(self._gemini_status)

        litellm_sub = Gtk.Label(label="LiteLLM (local)")
        litellm_sub.set_xalign(0)
        litellm_sub.set_margin_top(8)
        _attrs4 = Pango.AttrList()
        _attrs4.insert(
            Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold"))
        )
        litellm_sub.set_attributes(_attrs4)
        content.append(litellm_sub)

        litellm_url_label = Gtk.Label(label="Base URL")
        litellm_url_label.set_xalign(0)
        content.append(litellm_url_label)
        self._litellm_url_entry = Gtk.Entry()
        self._litellm_url_entry.set_text(
            self._config.get("litellm_base_url", "http://cerberus-ai:4000/v1")
        )
        content.append(self._litellm_url_entry)

        litellm_key_label = Gtk.Label(label="API key")
        litellm_key_label.set_xalign(0)
        content.append(litellm_key_label)
        self._litellm_key_entry = Gtk.PasswordEntry()
        self._litellm_key_entry.set_show_peek_icon(True)
        if self._config.get("litellm_api_key"):
            self._litellm_key_entry.set_text(self._config["litellm_api_key"])
        content.append(self._litellm_key_entry)

        litellm_whisper_label = Gtk.Label(label="Whisper model")
        litellm_whisper_label.set_xalign(0)
        content.append(litellm_whisper_label)
        self._litellm_whisper_entry = Gtk.Entry()
        self._litellm_whisper_entry.set_text(
            self._config.get("litellm_whisper_model", "whisper-turbo")
        )
        content.append(self._litellm_whisper_entry)

        litellm_chat_label = Gtk.Label(label="Chat model")
        litellm_chat_label.set_xalign(0)
        content.append(litellm_chat_label)
        self._litellm_chat_entry = Gtk.Entry()
        self._litellm_chat_entry.set_text(
            self._config.get("litellm_chat_model", "gemini")
        )
        content.append(self._litellm_chat_entry)

        litellm_test_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._litellm_test_btn = Gtk.Button(label="Test connection")
        self._litellm_test_btn.connect("clicked", self._on_test_litellm)
        litellm_test_row.append(self._litellm_test_btn)
        self._litellm_spinner = Gtk.Spinner()
        litellm_test_row.append(self._litellm_spinner)
        content.append(litellm_test_row)

        self._litellm_status = Gtk.Label(label="")
        self._litellm_status.set_xalign(0)
        self._litellm_status.set_wrap(True)
        self._litellm_status.add_css_class("error")
        content.append(self._litellm_status)

        content = _make_tab("Hotkeys")

        hotkeys_title = Gtk.Label(label="Hotkeys")
        hotkeys_title.add_css_class("title-4")
        hotkeys_title.set_xalign(0)
        content.append(hotkeys_title)

        self._capture_action: str | None = None
        self._capture_prev_combo: str | None = None
        self._capture_buttons: dict[str, Gtk.Button] = {}
        self._hotkey_values: dict[str, str] = {}
        self._hotkey_error_label = Gtk.Label(label="")
        self._hotkey_error_label.set_xalign(0)
        self._hotkey_error_label.add_css_class("error")
        self._hotkey_error_label.set_wrap(True)

        for action, cfg_key in HOTKEY_CONFIG_KEYS.items():
            self._hotkey_values[action] = self._config.get(
                cfg_key, HOTKEY_DEFAULTS[action]
            )

        _ACTION_ROWS = [
            ("Record Toggle", "record"),
            ("Stop Recording", "stop"),
            ("Conversation Mode", "conversation"),
            ("Reprocess Failed", "reprocess"),
            ("Feedback Toggle", "feedback"),
            ("Huddle Recording", "huddle"),
        ]
        for lbl_text, action in _ACTION_ROWS:
            content.append(self._make_hotkey_row(lbl_text, action))

        content.append(self._hotkey_error_label)

        reset_all_btn = Gtk.Button(label="Reset All Hotkeys to Defaults")
        reset_all_btn.connect("clicked", self._on_reset_all_hotkeys)
        content.append(reset_all_btn)

        content = _make_tab("Recording")
        # Re-scan input/output devices each time this tab is shown so devices
        # hot-plugged after the window opened (e.g. Bluetooth headsets) appear.
        content.connect("map", self._on_recording_tab_shown)

        vocab_title = Gtk.Label(label="Vocabulary (optional)")
        vocab_title.add_css_class("title-4")
        vocab_title.set_xalign(0)
        content.append(vocab_title)

        vocab_desc = Gtk.Label(
            label="Enter custom words or phrases, one per line. Leave empty to skip."
        )
        vocab_desc.set_xalign(0)
        vocab_desc.set_wrap(True)
        content.append(vocab_desc)

        vocab_scroll = Gtk.ScrolledWindow()
        vocab_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vocab_scroll.set_min_content_height(100)

        self._vocab_view = Gtk.TextView()
        self._vocab_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        vocab_scroll.set_child(self._vocab_view)
        content.append(vocab_scroll)

        vocab = self._config.get("vocabulary", [])
        if vocab:
            self._vocab_view.get_buffer().set_text("\n".join(vocab))

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(8)
        sep2.set_margin_bottom(8)
        content.append(sep2)

        audio_title = Gtk.Label(label="Audio")
        audio_title.add_css_class("title-4")
        audio_title.set_xalign(0)
        content.append(audio_title)

        mic_label = Gtk.Label(label="Input device")
        mic_label.set_xalign(0)
        content.append(mic_label)

        self._mic_combo = Gtk.ComboBoxText()
        self._mic_changed_id = self._mic_combo.connect("changed", self._on_mic_changed)
        _block_scroll(self._mic_combo)
        content.append(self._mic_combo)

        vu_label = Gtk.Label(label="Input level:")
        vu_label.set_xalign(0)
        vu_label.set_margin_top(4)
        content.append(vu_label)

        self._vu_bar = Gtk.LevelBar()
        self._vu_bar.set_min_value(0.0)
        self._vu_bar.set_max_value(1.0)
        self._vu_bar.set_value(0.0)
        self._vu_bar.set_margin_bottom(4)
        content.append(self._vu_bar)

        vu_hint = Gtk.Label(
            label="Speak to confirm your microphone is picking up audio."
        )
        vu_hint.set_xalign(0)
        vu_hint.set_wrap(True)
        vu_hint.add_css_class("dim-label")
        content.append(vu_hint)

        self._mic_error = Gtk.Label(label="")
        self._mic_error.set_xalign(0)
        self._mic_error.set_wrap(True)
        self._mic_error.add_css_class("error")
        content.append(self._mic_error)

        sink_label = Gtk.Label(label="Output device")
        sink_label.set_xalign(0)
        sink_label.set_margin_top(4)
        content.append(sink_label)
        self._sink_combo = Gtk.ComboBoxText()
        _block_scroll(self._sink_combo)
        content.append(self._sink_combo)

        sounds_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sounds_row.set_margin_top(4)
        sounds_label = Gtk.Label(label="Notification sounds")
        sounds_label.set_hexpand(True)
        sounds_label.set_xalign(0)
        self._sounds_switch = Gtk.Switch()
        self._sounds_switch.set_active(self._config.get("sounds_enabled", True))
        sounds_row.append(sounds_label)
        sounds_row.append(self._sounds_switch)
        content.append(sounds_row)

        dur_label = Gtk.Label(label="Max recording duration (seconds)")
        dur_label.set_xalign(0)
        dur_label.set_margin_top(4)
        content.append(dur_label)
        self._max_duration_spin = Gtk.SpinButton.new_with_range(10, 600, 10)
        self._max_duration_spin.set_value(
            self._config.get("max_recording_duration", 300)
        )
        _block_scroll_spin(self._max_duration_spin)
        content.append(self._max_duration_spin)

        silence_label = Gtk.Label(label="Silence auto-stop (seconds)")
        silence_label.set_xalign(0)
        content.append(silence_label)
        self._silence_spin = Gtk.SpinButton.new_with_range(1, 60, 1)
        self._silence_spin.set_value(self._config.get("silence_stop_duration", 10))
        _block_scroll_spin(self._silence_spin)
        content.append(self._silence_spin)

        sep3 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep3.set_margin_top(8)
        sep3.set_margin_bottom(8)
        content.append(sep3)

        trans_title = Gtk.Label(label="Transcription")
        trans_title.add_css_class("title-4")
        trans_title.set_xalign(0)
        content.append(trans_title)

        llm_model_label = Gtk.Label(label="LLM model")
        llm_model_label.set_xalign(0)
        llm_model_label.set_margin_top(4)
        content.append(llm_model_label)

        current_model = self._config.get("llm_model", LLM_MODELS[0])
        self._llm_model_list = list(LLM_MODELS)
        if current_model not in self._llm_model_list:
            self._llm_model_list.insert(0, current_model)
        string_list = Gtk.StringList.new(self._llm_model_list)
        self._llm_model_dropdown = Gtk.DropDown.new(string_list, None)
        self._llm_model_dropdown.set_selected(self._llm_model_list.index(current_model))
        content.append(self._llm_model_dropdown)

        timeout_label = Gtk.Label(label="Pipeline timeout (seconds)")
        timeout_label.set_xalign(0)
        timeout_label.set_margin_top(4)
        content.append(timeout_label)

        self._pipeline_timeout_spin = Gtk.SpinButton.new_with_range(10, 300, 10)
        self._pipeline_timeout_spin.set_value(self._config.get("pipeline_timeout", 60))
        _block_scroll_spin(self._pipeline_timeout_spin)
        content.append(self._pipeline_timeout_spin)

        # Processing sound section
        proc_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        proc_section.set_margin_top(4)

        proc_path_val = self._config.get("processing_sound_file", "") or ""
        self._proc_path_label = Gtk.Label(
            label=proc_path_val if proc_path_val else "Bundled default"
        )
        self._proc_path_label.set_xalign(0)
        self._proc_path_label.add_css_class("dim-label")
        self._proc_path_label.set_ellipsize(Pango.EllipsizeMode.START)

        proc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        processing_label = Gtk.Label(label="Processing sound")
        processing_label.set_hexpand(True)
        processing_label.set_xalign(0)
        proc_play_btn = Gtk.Button(label="▶")
        proc_play_btn.set_tooltip_text("Preview sound")
        proc_play_btn.connect(
            "clicked", self._on_play_sound, "processing.wav", "processing_sound_file"
        )
        proc_choose_btn = Gtk.Button(label="Choose file")
        proc_choose_btn.connect(
            "clicked",
            self._on_choose_sound,
            "processing_sound_file",
            self._proc_path_label,
        )
        self._processing_sound_switch = Gtk.Switch()
        self._processing_sound_switch.set_active(
            self._config.get("processing_sound_enabled", True)
        )
        proc_row.append(processing_label)
        proc_row.append(proc_play_btn)
        proc_row.append(proc_choose_btn)
        proc_row.append(self._processing_sound_switch)
        proc_section.append(proc_row)
        proc_section.append(self._proc_path_label)
        content.append(proc_section)

        # Success chime section
        success_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        success_section.set_margin_top(4)

        success_path_val = self._config.get("success_sound_file", "") or ""
        self._success_path_label = Gtk.Label(
            label=success_path_val if success_path_val else "Bundled default"
        )
        self._success_path_label.set_xalign(0)
        self._success_path_label.add_css_class("dim-label")
        self._success_path_label.set_ellipsize(Pango.EllipsizeMode.START)

        success_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        success_label = Gtk.Label(label="Success chime")
        success_label.set_hexpand(True)
        success_label.set_xalign(0)
        success_play_btn = Gtk.Button(label="▶")
        success_play_btn.set_tooltip_text("Preview sound")
        success_play_btn.connect(
            "clicked", self._on_play_sound, "success.wav", "success_sound_file"
        )
        success_choose_btn = Gtk.Button(label="Choose file")
        success_choose_btn.connect(
            "clicked",
            self._on_choose_sound,
            "success_sound_file",
            self._success_path_label,
        )
        self._success_sound_switch = Gtk.Switch()
        self._success_sound_switch.set_active(
            self._config.get("success_sound_enabled", True)
        )
        success_row.append(success_label)
        success_row.append(success_play_btn)
        success_row.append(success_choose_btn)
        success_row.append(self._success_sound_switch)
        success_section.append(success_row)
        success_section.append(self._success_path_label)
        content.append(success_section)

        terminals_label = Gtk.Label(label="Terminal emulators (one per line)")
        terminals_label.set_xalign(0)
        terminals_label.set_margin_top(4)
        content.append(terminals_label)

        terminals_scroll = Gtk.ScrolledWindow()
        terminals_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        terminals_scroll.set_min_content_height(80)
        self._terminals_view = Gtk.TextView()
        self._terminals_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        terminals_scroll.set_child(self._terminals_view)
        content.append(terminals_scroll)

        terminals = self._config.get("app_categories", {}).get("terminals", [])
        if terminals:
            self._terminals_view.get_buffer().set_text("\n".join(terminals))

        editors_label = Gtk.Label(label="Code editors (one per line)")
        editors_label.set_xalign(0)
        editors_label.set_margin_top(4)
        content.append(editors_label)

        editors_scroll = Gtk.ScrolledWindow()
        editors_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        editors_scroll.set_min_content_height(80)
        self._editors_view = Gtk.TextView()
        self._editors_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        editors_scroll.set_child(self._editors_view)
        content.append(editors_scroll)

        editors = self._config.get("app_categories", {}).get("editors", [])
        if editors:
            self._editors_view.get_buffer().set_text("\n".join(editors))

        sep_maint = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep_maint.set_margin_top(8)
        sep_maint.set_margin_bottom(8)
        content.append(sep_maint)

        maint_title = Gtk.Label(label="Maintenance")
        maint_title.add_css_class("title-4")
        maint_title.set_xalign(0)
        content.append(maint_title)

        history_header = Gtk.Label(label="History")
        attrs_bold = Pango.AttrList()
        attrs_bold.insert(
            Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold"))
        )
        history_header.set_attributes(attrs_bold)
        history_header.set_xalign(0)
        history_header.set_margin_top(4)
        content.append(history_header)

        max_entries_label = Gtk.Label(label="Max entries to keep")
        max_entries_label.set_xalign(0)
        content.append(max_entries_label)

        self._history_max_entries_spin = Gtk.SpinButton.new_with_range(5, 500, 1)
        self._history_max_entries_spin.set_value(
            self._config.get("history_max_entries", 20)
        )
        _block_scroll_spin(self._history_max_entries_spin)
        content.append(self._history_max_entries_spin)

        clear_history_btn = Gtk.Button(label="Clear All History")
        clear_history_btn.set_margin_top(4)
        clear_history_btn.connect("clicked", self._on_clear_all_history)
        content.append(clear_history_btn)

        clear_temp_btn = Gtk.Button(label="Clear Temp Audio Files")
        clear_temp_btn.set_margin_top(4)
        clear_temp_btn.connect("clicked", self._on_clear_temp_audio_files)
        content.append(clear_temp_btn)

        self._maint_status_label = Gtk.Label(label="")
        self._maint_status_label.set_xalign(0)
        self._maint_status_label.add_css_class("dim-label")
        content.append(self._maint_status_label)

        advanced_expander = Gtk.Expander(
            label="Advanced — changing the prompt may break post-processing"
        )
        advanced_expander.set_margin_top(8)
        content.append(advanced_expander)

        advanced_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        advanced_expander.set_child(advanced_box)

        prompt_label = Gtk.Label(label="LLM system prompt")
        prompt_label.set_xalign(0)
        prompt_label.set_margin_top(4)
        advanced_box.append(prompt_label)

        prompt_scroll = Gtk.ScrolledWindow()
        prompt_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        prompt_scroll.set_min_content_height(150)
        self._prompt_view = Gtk.TextView()
        self._prompt_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        prompt_scroll.set_child(self._prompt_view)
        advanced_box.append(prompt_scroll)

        self._prompt_view.get_buffer().set_text(
            self._config.get("llm_system_prompt", "")
        )

        reset_btn = Gtk.Button(label="Reset to Default")
        reset_btn.connect("clicked", self._on_reset_prompt)
        advanced_box.append(reset_btn)

        content = _make_tab("Conversation")

        conv_title = Gtk.Label(label="Conversation Mode")
        conv_title.add_css_class("title-4")
        conv_title.set_xalign(0)
        content.append(conv_title)

        mic_sens_label = Gtk.Label(label="Mic Sensitivity")
        mic_sens_label.set_xalign(0)
        content.append(mic_sens_label)

        self._conv_vu_level = 0.0
        self._conv_vu_canvas = Gtk.DrawingArea()
        self._conv_vu_canvas.set_hexpand(True)
        self._conv_vu_canvas.set_size_request(-1, 16)
        self._conv_vu_canvas.set_draw_func(self._draw_conv_mic, None)
        content.append(self._conv_vu_canvas)

        thresh_label = Gtk.Label(label="Silence threshold")
        thresh_label.set_xalign(0)
        thresh_label.set_margin_top(4)
        content.append(thresh_label)

        self._conv_threshold_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.001, 0.05, 0.001
        )
        self._conv_threshold_scale.set_value(
            self._config.get("conv_silence_rms_threshold", 0.005)
        )
        self._conv_threshold_scale.set_draw_value(False)
        self._conv_threshold_scale.connect(
            "value-changed", self._on_conv_threshold_changed
        )
        content.append(self._conv_threshold_scale)

        thresh_hint = Gtk.Label(
            label="Drag right until the marker sits just past your background noise."
        )
        thresh_hint.set_xalign(0)
        thresh_hint.set_wrap(True)
        thresh_hint.add_css_class("dim-label")
        content.append(thresh_hint)

        warn_label = Gtk.Label(label="Silence prompt timeout (seconds)")
        warn_label.set_xalign(0)
        warn_label.set_margin_top(8)
        content.append(warn_label)
        self._conv_warn_spin = Gtk.SpinButton.new_with_range(5, 300, 5)
        _block_scroll_spin(self._conv_warn_spin)
        self._conv_warn_spin.set_value(self._config.get("conv_silence_warn_sec", 30))
        content.append(self._conv_warn_spin)

        stop_label = Gtk.Label(label="Silence auto-stop timeout (seconds)")
        stop_label.set_xalign(0)
        content.append(stop_label)
        stop_hint = Gtk.Label(
            label="Auto-stops if you ignore the prompt. Must be > prompt timeout."
        )
        stop_hint.set_xalign(0)
        stop_hint.set_wrap(True)
        stop_hint.add_css_class("dim-label")
        content.append(stop_hint)
        self._conv_stop_spin = Gtk.SpinButton.new_with_range(10, 600, 5)
        _block_scroll_spin(self._conv_stop_spin)
        self._conv_stop_spin.set_value(self._config.get("conv_silence_stop_sec", 60))
        content.append(self._conv_stop_spin)

        save_label = Gtk.Label(label="Conversation Files Location")
        save_label.set_xalign(0)
        content.append(save_label)
        self._conv_save_entry = Gtk.Entry()
        self._conv_save_entry.set_text(
            self._config.get("conv_save_dir", "~/Documents/conversations")
        )
        content.append(self._conv_save_entry)

        feedback_label = Gtk.Label(label="In-session Feedback")
        feedback_label.set_xalign(0)
        content.append(feedback_label)
        self._feedback_combo = Gtk.ComboBoxText()
        _block_scroll(self._feedback_combo)
        self._feedback_combo.append("status_window", "Status Window")
        self._feedback_combo.append("tray_only", "Tray Only (quiet)")
        self._feedback_combo.set_active_id(
            self._config.get("conv_feedback_mode", "status_window")
        )
        content.append(self._feedback_combo)

        content = ai_tab

        qa_label = Gtk.Label(label="Max Q&A Rounds (before 'continue?' prompt)")
        qa_label.set_xalign(0)
        content.append(qa_label)
        self._qa_spin = Gtk.SpinButton()
        _block_scroll_spin(self._qa_spin)
        self._qa_spin.configure(
            Gtk.Adjustment.new(
                self._config.get("conv_max_qa_iterations", 3), 1, 20, 1, 1, 0
            ),
            1,
            0,
        )
        content.append(self._qa_spin)

        self._auto_analyze_check = Gtk.CheckButton(
            label="Auto-enable AI analysis in post-stop dialog"
        )
        self._auto_analyze_check.set_active(self._config.get("conv_auto_analyze", True))
        content.append(self._auto_analyze_check)

        conv_prompt_label = Gtk.Label(label="Default Analysis Prompt")
        conv_prompt_label.set_xalign(0)
        content.append(conv_prompt_label)
        conv_prompt_scroll = Gtk.ScrolledWindow()
        conv_prompt_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        conv_prompt_scroll.set_min_content_height(80)
        conv_prompt_scroll.set_max_content_height(120)
        self._conv_prompt_buf = Gtk.TextBuffer()
        self._conv_prompt_buf.set_text(self._config.get("conv_default_prompt", ""))
        conv_prompt_tv = Gtk.TextView(buffer=self._conv_prompt_buf)
        conv_prompt_tv.set_wrap_mode(Gtk.WrapMode.WORD)
        conv_prompt_scroll.set_child(conv_prompt_tv)
        content.append(conv_prompt_scroll)

        qq_label = Gtk.Label(label="Qualifying Questions (one per line)")
        qq_label.set_xalign(0)
        content.append(qq_label)
        qq_sub = Gtk.Label(
            label="Shown in the post-stop dialog to help calibrate AI response complexity"
        )
        qq_sub.add_css_class("caption")
        qq_sub.set_xalign(0)
        content.append(qq_sub)
        qq_scroll = Gtk.ScrolledWindow()
        qq_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        qq_scroll.set_min_content_height(100)
        qq_scroll.set_max_content_height(160)
        self._conv_qq_buf = Gtk.TextBuffer()
        _default_qq = [
            "Who is the intended audience for this content?",
            "What level of technical detail is appropriate?",
            "What is the primary purpose of this conversation?",
            "Should the output be formal or informal in tone?",
            "Are there specific topics or sections to prioritize?",
        ]
        existing_qq = self._config.get("conv_qualifying_questions", _default_qq)
        self._conv_qq_buf.set_text(
            "\n".join(existing_qq) if isinstance(existing_qq, list) else existing_qq
        )
        qq_tv = Gtk.TextView(buffer=self._conv_qq_buf)
        qq_tv.set_wrap_mode(Gtk.WrapMode.WORD)
        qq_scroll.set_child(qq_tv)
        content.append(qq_scroll)

        content = _make_tab("Integrations")

        integrations_title = Gtk.Label(label="Integrations")
        integrations_title.add_css_class("title-4")
        integrations_title.set_xalign(0)
        content.append(integrations_title)

        slack_sub = Gtk.Label(label="Slack")
        slack_sub.set_xalign(0)
        _attrs_slack = Pango.AttrList()
        _attrs_slack.insert(
            Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold"))
        )
        slack_sub.set_attributes(_attrs_slack)
        slack_sub.set_margin_top(4)
        content.append(slack_sub)

        ws_label = Gtk.Label(label="Connected Workspaces")
        ws_label.set_xalign(0)
        content.append(ws_label)

        self._workspace_listbox = Gtk.ListBox()
        self._workspace_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._workspace_listbox.add_css_class("boxed-list")
        content.append(self._workspace_listbox)
        self._refresh_workspace_list()

        ws_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ws_btn_row.set_margin_top(4)
        self._add_workspace_btn = Gtk.Button(label="Add Workspace")
        self._add_workspace_btn.connect("clicked", self._on_add_workspace)
        ws_btn_row.append(self._add_workspace_btn)
        self._disconnect_workspace_btn = Gtk.Button(label="Disconnect")
        self._disconnect_workspace_btn.add_css_class("destructive-action")
        self._disconnect_workspace_btn.connect("clicked", self._on_disconnect_workspace)
        ws_btn_row.append(self._disconnect_workspace_btn)
        content.append(ws_btn_row)

        auto_detect_label = Gtk.Label(label="Huddle Auto-Detect")
        auto_detect_label.set_xalign(0)
        auto_detect_label.set_margin_top(8)
        content.append(auto_detect_label)
        self._huddle_auto_detect_combo = Gtk.ComboBoxText()
        _block_scroll(self._huddle_auto_detect_combo)
        self._huddle_auto_detect_combo.append("manual", "Manual hotkey only")
        self._huddle_auto_detect_combo.append("prompt", "Prompt on detect")
        self._huddle_auto_detect_combo.append("always", "Auto always")
        self._huddle_auto_detect_combo.set_active_id(
            self._config.get("slack_huddle_auto_detect", "prompt")
        )
        content.append(self._huddle_auto_detect_combo)

        activation_label = Gtk.Label(label="Activation Word")
        activation_label.set_xalign(0)
        activation_label.set_margin_top(4)
        content.append(activation_label)
        self._slack_activation_entry = Gtk.Entry()
        self._slack_activation_entry.set_text(
            self._config.get("slack_activation_word", "conyo")
        )
        content.append(self._slack_activation_entry)

        confidence_label = Gtk.Label(label="Confidence Threshold")
        confidence_label.set_xalign(0)
        confidence_label.set_margin_top(4)
        content.append(confidence_label)
        self._slack_confidence_spin = Gtk.SpinButton.new_with_range(0.0, 1.0, 0.05)
        self._slack_confidence_spin.set_value(
            self._config.get("slack_confidence_threshold", 0.6)
        )
        _block_scroll_spin(self._slack_confidence_spin)
        content.append(self._slack_confidence_spin)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_start(24)
        btn_row.set_margin_end(24)
        btn_row.set_margin_top(8)
        btn_row.set_margin_bottom(16)
        outer.append(btn_row)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        btn_row.append(cancel_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_row.append(spacer)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        btn_row.append(save_btn)

        self._dirty = False
        self._enumerate_microphones()
        self._enumerate_sinks()
        self._connect_change_signals()

    def _on_recording_tab_shown(self, _widget):
        # Re-scan devices, preserving the current (possibly unsaved) selection.
        idx = self._mic_combo.get_active()
        prev = self._mics[idx]["name"] if 0 <= idx < len(self._mics) else ""
        self._enumerate_microphones()
        self._enumerate_sinks()
        if prev:
            for i, mic in enumerate(self._mics):
                if mic["name"] == prev:
                    self._mic_combo.handler_block(self._mic_changed_id)
                    self._mic_combo.set_active(i)
                    self._mic_combo.handler_unblock(self._mic_changed_id)
                    break

    def _enumerate_microphones(self):
        self._mic_combo.handler_block(self._mic_changed_id)
        self._mic_combo.remove_all()
        self._mic_error.set_text("")
        try:
            self._mics = list_microphones()
        except pulsectl.PulseError:
            self._mic_error.set_text(
                "Could not enumerate audio devices. Is PulseAudio/PipeWire running?"
            )
            self._mics = []
            self._mic_combo.handler_unblock(self._mic_changed_id)
            return

        current = self._config.get("microphone", "")
        for i, mic in enumerate(self._mics):
            self._mic_combo.append_text(mic["description"])
            if mic["name"] == current:
                self._mic_combo.set_active(i)

        if self._mic_combo.get_active() == -1 and self._mics:
            self._mic_combo.set_active(0)

        self._mic_combo.handler_unblock(self._mic_changed_id)
        # Defer VU start until after window is presented and mapped
        GLib.idle_add(self._restart_vu_meter)

    def _enumerate_sinks(self):
        from linux_speech_flow.audio import list_sinks

        self._sinks = list_sinks()
        self._sink_combo.remove_all()
        self._sink_combo.append_text("System default")
        current = self._config.get("sounds_output_device", "")
        selected_idx = 0
        for i, sink in enumerate(self._sinks):
            self._sink_combo.append_text(sink["description"])
            if sink["name"] == current:
                selected_idx = i + 1
        self._sink_combo.set_active(selected_idx)

    def _on_mic_changed(self, _combo):
        self._restart_vu_meter()

    def _restart_vu_meter(self):
        self._stop_vu_meter()
        active = self._mic_combo.get_active()
        if active >= 0 and self._mics:
            self._start_vu_meter(self._mics[active]["name"])

    def _start_vu_meter(self, source_name: str):
        self._vu_stop = threading.Event()
        threading.Thread(
            target=self._vu_worker, args=(source_name,), daemon=True
        ).start()

    def _stop_vu_meter(self):
        if hasattr(self, "_vu_stop"):
            self._vu_stop.set()
        if hasattr(self, "_vu_proc") and self._vu_proc:
            try:
                self._vu_proc.terminate()
                self._vu_proc.wait(timeout=1)
            except Exception:
                pass
            self._vu_proc = None

    def _vu_worker(self, source_name: str):
        RATE, CHUNK = 16000, 800
        cmd = [
            "parec",
            "--raw",
            "--channels=1",
            "--format=s16le",
            f"--rate={RATE}",
            "--latency-msec=50",
            "-d",
            source_name,
        ]
        self._vu_proc = None
        try:
            self._vu_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            while not self._vu_stop.is_set():
                data = self._vu_proc.stdout.read(CHUNK * 2)
                if not data:
                    break
                samples = struct.unpack(f"{len(data) // 2}h", data)
                rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0
                GLib.idle_add(self._update_vu, min(1.0, rms * 12))
        except Exception:
            pass
        finally:
            if self._vu_proc:
                try:
                    self._vu_proc.terminate()
                    self._vu_proc.wait(timeout=1)
                except Exception:
                    pass
                self._vu_proc = None

    def _update_vu(self, level: float):
        self._vu_bar.set_value(level)
        self._conv_vu_level = level
        self._conv_vu_canvas.queue_draw()
        return False

    def _draw_conv_mic(self, area, cr, width, height, _data) -> None:
        from linux_speech_flow.conversation_recorder import RMS_DISPLAY_SCALE

        thresh = self._conv_threshold_scale.get_value()
        thresh_x = min(1.0, thresh * RMS_DISPLAY_SCALE) * width
        fill_w = self._conv_vu_level * width
        cr.set_source_rgba(0.2, 0.2, 0.2, 0.4)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        if fill_w > 0:
            if fill_w <= thresh_x:
                cr.set_source_rgba(0.2, 0.5, 1.0, 0.8)
                cr.rectangle(0, 0, fill_w, height)
                cr.fill()
            else:
                cr.set_source_rgba(0.2, 0.5, 1.0, 0.8)
                cr.rectangle(0, 0, thresh_x, height)
                cr.fill()
                cr.set_source_rgba(1.0, 0.55, 0.1, 0.9)
                cr.rectangle(thresh_x, 0, fill_w - thresh_x, height)
                cr.fill()
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

    def _on_conv_threshold_changed(self, _scale) -> None:
        self._conv_vu_canvas.queue_draw()
        self._mark_dirty()

    def _set_status(self, label: Gtk.Label, ok: bool, message: str):
        label.remove_css_class("error")
        label.remove_css_class("success")
        label.add_css_class("success" if ok else "error")
        label.set_text(message)

    def _on_validate(self, _btn):
        key = self._api_key_entry.get_text().strip()
        self._groq_status.set_text("")
        self._groq_spinner.start()
        self._validate_btn.set_sensitive(False)

        def run():
            result = validate_api_key(key)
            GLib.idle_add(self._on_validation_done, result)
            return False

        threading.Thread(target=run, daemon=True).start()

    def _on_validation_done(self, result: dict):
        self._groq_spinner.stop()
        self._validate_btn.set_sensitive(True)
        if result["ok"]:
            self._set_status(self._groq_status, True, "API key is valid.")
        else:
            self._set_status(
                self._groq_status, False, result.get("message", "Validation failed")
            )
        return False

    def _on_test_grok(self, _btn):
        key = self._grok_key_entry.get_text().strip()
        self._grok_status.set_text("")
        self._grok_spinner.start()
        self._grok_test_btn.set_sensitive(False)

        def run():
            try:
                from openai import OpenAI

                client = OpenAI(api_key=key, base_url="https://api.x.ai/v1")
                client.models.list()
                GLib.idle_add(self._on_test_grok_done, {"ok": True})
            except Exception as exc:
                GLib.idle_add(
                    self._on_test_grok_done, {"ok": False, "message": str(exc)}
                )
            return False

        threading.Thread(target=run, daemon=True).start()

    def _on_test_grok_done(self, result: dict):
        self._grok_spinner.stop()
        self._grok_test_btn.set_sensitive(True)
        if result["ok"]:
            self._set_status(self._grok_status, True, "API key is valid.")
        else:
            self._set_status(
                self._grok_status, False, result.get("message", "Test failed")
            )
        return False

    def _on_test_gemini(self, _btn):
        key = self._gemini_key_entry.get_text().strip()
        self._gemini_status.set_text("")
        self._gemini_spinner.start()
        self._gemini_test_btn.set_sensitive(False)

        def run():
            try:
                from google import genai

                client = genai.Client(api_key=key)
                list(client.models.list())
                GLib.idle_add(self._on_test_gemini_done, {"ok": True})
            except Exception as exc:
                GLib.idle_add(
                    self._on_test_gemini_done, {"ok": False, "message": str(exc)}
                )
            return False

        threading.Thread(target=run, daemon=True).start()

    def _on_test_gemini_done(self, result: dict):
        self._gemini_spinner.stop()
        self._gemini_test_btn.set_sensitive(True)
        if result["ok"]:
            self._set_status(self._gemini_status, True, "API key is valid.")
        else:
            self._set_status(
                self._gemini_status, False, result.get("message", "Test failed")
            )
        return False

    def _on_test_litellm(self, _btn):
        base_url = self._litellm_url_entry.get_text().strip().rstrip("/")
        key = self._litellm_key_entry.get_text().strip()
        self._litellm_status.set_text("")
        self._litellm_spinner.start()
        self._litellm_test_btn.set_sensitive(False)

        def run():
            import requests

            try:
                resp = requests.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    GLib.idle_add(self._on_test_litellm_done, {"ok": True})
                else:
                    GLib.idle_add(
                        self._on_test_litellm_done,
                        {"ok": False, "message": f"HTTP {resp.status_code}"},
                    )
            except Exception as exc:
                GLib.idle_add(
                    self._on_test_litellm_done, {"ok": False, "message": str(exc)}
                )
            return False

        threading.Thread(target=run, daemon=True).start()

    def _on_test_litellm_done(self, result: dict):
        self._litellm_spinner.stop()
        self._litellm_test_btn.set_sensitive(True)
        if result["ok"]:
            self._set_status(self._litellm_status, True, "Connection OK.")
        else:
            self._set_status(
                self._litellm_status, False, result.get("message", "Test failed")
            )
        return False

    def _on_save(self, _btn):
        self._stop_vu_meter()
        buf = self._vocab_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        vocab = [line.strip() for line in text.splitlines() if line.strip()]

        active = self._mic_combo.get_active()
        mic_name = self._mics[active]["name"] if self._mics and active >= 0 else ""

        config = load_config()
        config["groq_api_key"] = self._api_key_entry.get_text().strip()
        config["microphone"] = mic_name
        config["vocabulary"] = vocab
        config["sounds_enabled"] = self._sounds_switch.get_active()
        sink_active = self._sink_combo.get_active()
        if sink_active <= 0 or not self._sinks:
            config["sounds_output_device"] = ""
        else:
            config["sounds_output_device"] = self._sinks[sink_active - 1]["name"]
        config["max_recording_duration"] = int(self._max_duration_spin.get_value())
        config["silence_stop_duration"] = int(self._silence_spin.get_value())
        config["llm_model"] = self._llm_model_list[
            self._llm_model_dropdown.get_selected()
        ]
        config["pipeline_timeout"] = int(self._pipeline_timeout_spin.get_value())
        config["processing_sound_enabled"] = self._processing_sound_switch.get_active()
        config["processing_sound_file"] = self._config.get("processing_sound_file", "")
        config["success_sound_enabled"] = self._success_sound_switch.get_active()
        config["success_sound_file"] = self._config.get("success_sound_file", "")
        config["history_max_entries"] = int(self._history_max_entries_spin.get_value())
        config["grok_api_key"] = self._grok_key_entry.get_text().strip()
        config["gemini_api_key"] = self._gemini_key_entry.get_text().strip()
        config["provider_mode"] = (
            "litellm" if self._provider_litellm_radio.get_active() else "cloud"
        )
        config["litellm_base_url"] = self._litellm_url_entry.get_text().strip()
        config["litellm_api_key"] = self._litellm_key_entry.get_text().strip()
        config["litellm_whisper_model"] = self._litellm_whisper_entry.get_text().strip()
        config["litellm_chat_model"] = self._litellm_chat_entry.get_text().strip()
        config["conv_silence_rms_threshold"] = self._conv_threshold_scale.get_value()
        config["conv_silence_warn_sec"] = int(self._conv_warn_spin.get_value())
        config["conv_silence_stop_sec"] = int(self._conv_stop_spin.get_value())
        config["conv_save_dir"] = self._conv_save_entry.get_text().strip()
        config["conv_feedback_mode"] = (
            self._feedback_combo.get_active_id() or "status_window"
        )
        config["conv_max_qa_iterations"] = int(self._qa_spin.get_value())
        config["conv_auto_analyze"] = self._auto_analyze_check.get_active()
        config["conv_default_prompt"] = self._conv_prompt_buf.get_text(
            self._conv_prompt_buf.get_start_iter(),
            self._conv_prompt_buf.get_end_iter(),
            False,
        )
        _qq_raw = self._conv_qq_buf.get_text(
            self._conv_qq_buf.get_start_iter(), self._conv_qq_buf.get_end_iter(), False
        )
        config["conv_qualifying_questions"] = [
            q.strip() for q in _qq_raw.splitlines() if q.strip()
        ]

        def _buf_lines(view):
            buf = view.get_buffer()
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
            return [line.strip() for line in text.splitlines() if line.strip()]

        config["app_categories"] = {
            "terminals": _buf_lines(self._terminals_view),
            "editors": _buf_lines(self._editors_view),
        }

        prompt_buf = self._prompt_view.get_buffer()
        config["llm_system_prompt"] = prompt_buf.get_text(
            prompt_buf.get_start_iter(), prompt_buf.get_end_iter(), False
        )
        for action, cfg_key in HOTKEY_CONFIG_KEYS.items():
            config[cfg_key] = self._hotkey_values[action]
        config["slack_huddle_auto_detect"] = (
            self._huddle_auto_detect_combo.get_active_id() or "prompt"
        )
        config["slack_activation_word"] = (
            self._slack_activation_entry.get_text().strip()
        )
        config["slack_confidence_threshold"] = self._slack_confidence_spin.get_value()
        save_config(config)
        self._closing = True
        self.close()

    def _on_play_sound(self, _btn, default_name: str, config_key: str):
        from linux_speech_flow.sounds import play_sound

        config = load_config()
        output_device = config.get("sounds_output_device", "")
        custom_path = self._config.get(config_key, "") or None
        play_sound(default_name, output_device, True, custom_path)

    def _on_choose_sound(self, _btn, config_key: str, path_label: Gtk.Label):
        native = Gtk.FileChooserNative.new(
            "Choose sound file",
            self,
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel",
        )
        filt = Gtk.FileFilter()
        filt.set_name("WAV files (*.wav)")
        filt.add_pattern("*.wav")
        native.add_filter(filt)
        current = self._config.get(config_key, "")
        if current:
            native.set_file(Gio.File.new_for_path(current))
        self._active_chooser = native  # prevent GC before response
        native.connect("response", self._on_sound_chosen, config_key, path_label)
        native.show()

    def _on_sound_chosen(
        self, dialog, response, config_key: str, path_label: Gtk.Label
    ):
        self._active_chooser = None
        if response == Gtk.ResponseType.ACCEPT:
            f = dialog.get_file()
            path = f.get_path() if f else ""
            self._config[config_key] = path or ""
            path_label.set_text(path if path else "Bundled default")

    def _on_reset_prompt(self, _btn):
        from linux_speech_flow.config import DEFAULT_CONFIG

        self._prompt_view.get_buffer().set_text(DEFAULT_CONFIG["llm_system_prompt"])

    def _mark_dirty(self, *_):
        self._dirty = True

    def _connect_change_signals(self):
        md = self._mark_dirty
        self._api_key_entry.connect("changed", md)
        self._vocab_view.get_buffer().connect("changed", md)
        self._mic_combo.connect("changed", md)
        self._sink_combo.connect("changed", md)
        self._sounds_switch.connect("notify::active", md)
        self._max_duration_spin.connect("value-changed", md)
        self._silence_spin.connect("value-changed", md)
        self._llm_model_dropdown.connect("notify::selected", md)
        self._pipeline_timeout_spin.connect("value-changed", md)
        self._processing_sound_switch.connect("notify::active", md)
        self._success_sound_switch.connect("notify::active", md)
        self._terminals_view.get_buffer().connect("changed", md)
        self._editors_view.get_buffer().connect("changed", md)
        self._prompt_view.get_buffer().connect("changed", md)
        self._history_max_entries_spin.connect("value-changed", md)
        self._grok_key_entry.connect("changed", md)
        self._gemini_key_entry.connect("changed", md)
        self._provider_cloud_radio.connect("toggled", md)
        self._litellm_url_entry.connect("changed", md)
        self._litellm_key_entry.connect("changed", md)
        self._litellm_whisper_entry.connect("changed", md)
        self._litellm_chat_entry.connect("changed", md)
        self._conv_warn_spin.connect("value-changed", md)
        self._conv_stop_spin.connect("value-changed", md)
        self._conv_save_entry.connect("changed", md)
        self._feedback_combo.connect("changed", md)
        self._qa_spin.connect("value-changed", md)
        self._auto_analyze_check.connect("toggled", md)
        self._conv_prompt_buf.connect("changed", md)
        self._conv_qq_buf.connect("changed", md)
        self._huddle_auto_detect_combo.connect("changed", md)
        self._slack_activation_entry.connect("changed", md)
        self._slack_confidence_spin.connect("value-changed", md)

    def _make_hotkey_row(self, label_text: str, action: str) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl = Gtk.Label(label=label_text)
        lbl.set_hexpand(True)
        lbl.set_xalign(0)
        btn = Gtk.Button(label=combo_display(self._hotkey_values[action]))
        btn.connect("clicked", self._on_capture_click, action)
        self._capture_buttons[action] = btn
        reset_btn = Gtk.Button()
        reset_btn.set_icon_name("view-refresh-symbolic")
        reset_btn.set_tooltip_text(
            f"Reset to default ({combo_display(HOTKEY_DEFAULTS[action])})"
        )
        reset_btn.connect("clicked", self._on_reset_hotkey, action)
        row.append(lbl)
        row.append(btn)
        row.append(reset_btn)
        return row

    def _on_capture_click(self, _btn, action: str) -> None:
        if self._capture_action is not None:
            self._cancel_capture()
        self._capture_action = action
        self._capture_prev_combo = self._hotkey_values.get(action)
        self._capture_buttons[action].set_label("Press keys...")
        self._hotkey_error_label.set_text("")
        self.set_focus(None)

    def _handle_capture_key(self, keyval: int, state) -> bool:
        from gi.repository import Gdk as _Gdk

        global _GTK_MODIFIER_KEYSYMS
        try:
            _GTK_MODIFIER_KEYSYMS  # noqa: B018 — probe: reference to trigger NameError on first use
        except NameError:
            _GTK_MODIFIER_KEYSYMS = frozenset(
                {
                    _Gdk.KEY_Control_L,
                    _Gdk.KEY_Control_R,
                    _Gdk.KEY_Alt_L,
                    _Gdk.KEY_Alt_R,
                    _Gdk.KEY_Shift_L,
                    _Gdk.KEY_Shift_R,
                    _Gdk.KEY_Super_L,
                    _Gdk.KEY_Super_R,
                    _Gdk.KEY_ISO_Level3_Shift,
                    _Gdk.KEY_Caps_Lock,
                    _Gdk.KEY_Num_Lock,
                }
            )

        if keyval == _Gdk.KEY_Escape:
            self._cancel_capture()
            return True

        if keyval in _GTK_MODIFIER_KEYSYMS:
            return True

        mods = set()
        if state & _Gdk.ModifierType.CONTROL_MASK:
            mods.add("ctrl")
        if state & _Gdk.ModifierType.ALT_MASK:
            mods.add("alt")
        if state & _Gdk.ModifierType.SHIFT_MASK:
            mods.add("shift")
        if state & _Gdk.ModifierType.SUPER_MASK:
            mods.add("super")

        if not mods:
            self._hotkey_error_label.set_text(
                "Combo must include at least one modifier (Ctrl, Alt, Shift, Super)"
            )
            return True

        key_id = self._gdk_keyval_to_id(keyval)
        if key_id is None:
            return True

        mod_order = ["ctrl", "alt", "shift", "super"]
        combo_str = "+".join(m for m in mod_order if m in mods) + "+" + key_id
        self._accept_capture(combo_str)
        return True

    @staticmethod
    def _gdk_keyval_to_id(keyval: int) -> str | None:
        from gi.repository import Gdk as _Gdk

        _SPECIAL = {
            _Gdk.KEY_Escape: "esc",
            _Gdk.KEY_Delete: "delete",
            _Gdk.KEY_Return: "enter",
            _Gdk.KEY_Tab: "tab",
            _Gdk.KEY_space: "space",
            _Gdk.KEY_Left: "left",
            _Gdk.KEY_Right: "right",
            _Gdk.KEY_Up: "up",
            _Gdk.KEY_Down: "down",
            _Gdk.KEY_Home: "home",
            _Gdk.KEY_End: "end",
            _Gdk.KEY_Page_Up: "page_up",
            _Gdk.KEY_Page_Down: "page_down",
            _Gdk.KEY_Insert: "insert",
            _Gdk.KEY_F1: "f1",
            _Gdk.KEY_F2: "f2",
            _Gdk.KEY_F3: "f3",
            _Gdk.KEY_F4: "f4",
            _Gdk.KEY_F5: "f5",
            _Gdk.KEY_F6: "f6",
            _Gdk.KEY_F7: "f7",
            _Gdk.KEY_F8: "f8",
            _Gdk.KEY_F9: "f9",
            _Gdk.KEY_F10: "f10",
            _Gdk.KEY_F11: "f11",
            _Gdk.KEY_F12: "f12",
        }
        if keyval in _SPECIAL:
            return _SPECIAL[keyval]
        char = chr(keyval).lower()
        if char.isalpha() or char.isdigit():
            return char
        return None

    def _accept_capture(self, combo_str: str) -> None:
        action = self._capture_action
        if action is None:
            return

        if combo_str in DANGEROUS_COMBOS:
            self._hotkey_error_label.set_text(
                f"{combo_display(combo_str)} is reserved by the system"
            )
            self._cancel_capture()
            return

        for other_action, current_combo in self._hotkey_values.items():
            if other_action == action:
                continue
            if current_combo == combo_str:
                self._hotkey_error_label.set_text(
                    f"{combo_display(combo_str)} is already used for {HOTKEY_ACTION_LABELS[other_action]}"
                )
                self._cancel_capture()
                return

        self._hotkey_error_label.set_text("")
        self._capture_action = None
        self._apply_binding(action, combo_str)

    def _cancel_capture(self) -> None:
        action = self._capture_action
        self._capture_action = None
        if action and action in self._capture_buttons:
            prev = self._capture_prev_combo or HOTKEY_DEFAULTS.get(action, "")
            self._capture_buttons[action].set_label(combo_display(prev))

    def _apply_binding(self, action: str, combo_str: str) -> None:
        self._hotkey_values[action] = combo_str
        if action in self._capture_buttons:
            self._capture_buttons[action].set_label(combo_display(combo_str))
        if self._hotkey_manager:
            self._hotkey_manager.apply_binding_override(action, combo_str)
        self._mark_dirty()

    def _on_reset_hotkey(self, _btn, action: str) -> None:
        if self._capture_action is not None:
            self._cancel_capture()
        self._hotkey_error_label.set_text("")
        self._apply_binding(action, HOTKEY_DEFAULTS[action])

    def _on_reset_all_hotkeys(self, _btn) -> None:
        if self._capture_action is not None:
            self._cancel_capture()
        self._hotkey_error_label.set_text("")
        for action, default_combo in HOTKEY_DEFAULTS.items():
            self._apply_binding(action, default_combo)

    def _on_clear_all_history(self, _btn):
        dialog = Gtk.Window(title="Confirm Clear History")
        dialog.set_modal(True)
        dialog.set_transient_for(self)
        dialog.set_default_size(360, 140)

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
            HistoryStore().clear_all()
            self._maint_status_label.set_label("History cleared.")

        clear_btn.connect("clicked", _do_clear)
        btn_row.append(clear_btn)

        dialog.present()

    def _on_clear_temp_audio_files(self, _btn):
        count = 0
        if FAILED_DIR.exists():
            for wav_file in FAILED_DIR.glob("*.wav"):
                try:
                    wav_file.unlink()
                    count += 1
                except OSError:
                    pass
        self._maint_status_label.set_label(
            f"Temp audio files cleared ({count} removed)."
        )

    def _is_dirty(self):
        return self._dirty

    def _show_unsaved_dialog(self):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Save changes?",
            secondary_text="Your settings have been modified.",
        )
        dialog.add_button("Discard", Gtk.ResponseType.REJECT)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        save_btn = dialog.add_button("Save", Gtk.ResponseType.ACCEPT)
        save_btn.add_css_class("suggested-action")
        dialog.connect("response", self._on_unsaved_response)
        dialog.present()

    def _on_unsaved_response(self, dialog, response):
        dialog.destroy()
        if response == Gtk.ResponseType.ACCEPT:
            self._on_save(None)
        elif response == Gtk.ResponseType.REJECT:
            self._closing = True
            self.close()

    def _on_key_pressed(self, _ctrl, keyval, _keycode, state):
        if self._capture_action:
            return self._handle_capture_key(keyval, state)
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _refresh_workspace_list(self):
        while True:
            row = self._workspace_listbox.get_row_at_index(0)
            if row is None:
                break
            self._workspace_listbox.remove(row)

        from linux_speech_flow.slack_manager import SlackManager

        workspaces = SlackManager().get_workspaces()
        for team_id, ws in workspaces.items():
            team_name = ws.get("team_name", team_id)
            channel_id = ws.get("channel_id", "")
            lbl_text = team_name
            if channel_id:
                lbl_text += f" — {channel_id}"
            row = Gtk.ListBoxRow()
            row._team_id = team_id
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row_box.set_margin_start(8)
            row_box.set_margin_end(8)
            row_box.set_margin_top(4)
            row_box.set_margin_bottom(4)
            lbl = Gtk.Label(label=lbl_text)
            lbl.set_xalign(0)
            lbl.set_hexpand(True)
            row_box.append(lbl)
            edit_btn = Gtk.Button(label="Edit")
            edit_btn.connect(
                "clicked", lambda _b, tid=team_id, w=ws: self._on_edit_workspace(tid, w)
            )
            row_box.append(edit_btn)
            row.set_child(row_box)
            self._workspace_listbox.append(row)

    def _on_add_workspace(self, _btn):
        dialog = AddWorkspaceDialog(self)
        dialog.connect("workspace-added", self._on_workspace_added)
        dialog.present()

    def _on_workspace_added(self, _dialog):
        self._refresh_workspace_list()
        self._mark_dirty()

    def _on_disconnect_workspace(self, _btn):
        selected = self._workspace_listbox.get_selected_row()
        if selected is None:
            return
        team_id = getattr(selected, "_team_id", None)
        if not team_id:
            return
        from linux_speech_flow.slack_manager import SlackManager

        SlackManager().remove_workspace(team_id)
        self._refresh_workspace_list()
        self._mark_dirty()

    def _on_edit_workspace(self, team_id: str, workspace_data: dict):
        dialog = AddWorkspaceDialog(
            self, existing_team_id=team_id, existing_data=workspace_data
        )
        dialog.connect("workspace-added", self._on_workspace_added)
        dialog.present()

    def _on_close(self, _window):
        if self._closing:
            self._stop_vu_meter()
            return False
        if self._is_dirty():
            self._show_unsaved_dialog()
            return True
        self._stop_vu_meter()
        return False


class AddWorkspaceDialog(Gtk.Window):
    """Guided dialog for connecting a Slack workspace via bot + app-level tokens."""

    __gsignals__ = {
        "workspace-added": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, parent, existing_team_id=None, existing_data=None):
        title = "Edit Slack Workspace" if existing_data else "Connect Slack Workspace"
        super().__init__(title=title, modal=True)
        self._existing_team_id = existing_team_id
        self.set_transient_for(parent)
        self.set_default_size(520, 740)
        self.set_resizable(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer.append(scroll)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(16)
        box.set_margin_bottom(8)
        scroll.set_child(box)

        steps = [
            "Open a web browser and go to api.slack.com/apps. Click \u201cCreate New App\u201d \u2192 \u201cFrom scratch\u201d. Enter any name (e.g. Linux Speech Flow), choose your Slack workspace, then click \u201cCreate App\u201d.",
            "In the left sidebar, click \u201cOAuth & Permissions\u201d. Scroll down to \u201cScopes\u201d \u2192 \u201cBot Token Scopes\u201d. Click \u201cAdd an OAuth Scope\u201d three times and add: chat:write, chat:write.public, and files:write.",
            "Scroll to the top of the \u201cOAuth & Permissions\u201d page. Click \u201cInstall to [Your Workspace]\u201d, then \u201cAllow\u201d. Copy the \u201cBot User OAuth Token\u201d (starts with xoxb-) and paste it in the field below. Then in Slack, go to your target channel and type /invite @YourAppName to add the bot.",
            "In the left sidebar, click \u201cSocket Mode\u201d and toggle on \u201cEnable Socket Mode\u201d.",
            "In the left sidebar, click \u201cBasic Information\u201d. Scroll down to \u201cApp-Level Tokens\u201d. Click \u201cGenerate Token and Scopes\u201d. Enter any name, click \u201cAdd Scope\u201d and choose connections:write, then click \u201cGenerate\u201d. Copy the token (starts with xapp-) and paste it in the field below.",
            "In the left sidebar, click \u201cEvent Subscriptions\u201d and toggle on \u201cEnable Events\u201d. Under \u201cSubscribe to bot events\u201d, click \u201cAdd Bot User Event\u201d and add user_huddle_changed. Click \u201cSave Changes\u201d.",
            "Find your Slack User ID: in the Slack app, click your profile picture \u2192 \u201cView profile\u201d \u2192 click the \u2026 menu \u2192 \u201cCopy member ID\u201d. Paste it in the \u201cYour Slack User ID\u201d field below.",
        ]
        for i, step_text in enumerate(steps, start=1):
            step_lbl = Gtk.Label(label=f"{i}. {step_text}")
            step_lbl.set_xalign(0)
            step_lbl.set_wrap(True)
            step_lbl.set_margin_bottom(4)
            box.append(step_lbl)

        bot_lbl = Gtk.Label(label="Bot User OAuth Token")
        bot_lbl.set_xalign(0)
        bot_lbl.set_margin_top(8)
        box.append(bot_lbl)
        self._bot_token_entry = Gtk.Entry()
        self._bot_token_entry.set_property("placeholder-text", "xoxb-...")
        box.append(self._bot_token_entry)

        app_lbl = Gtk.Label(label="App-Level Token")
        app_lbl.set_xalign(0)
        app_lbl.set_margin_top(4)
        box.append(app_lbl)

        app_token_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._app_token_entry = Gtk.PasswordEntry()
        self._app_token_entry.set_show_peek_icon(True)
        self._app_token_entry.set_property("placeholder-text", "xapp-...")
        self._app_token_entry.set_hexpand(True)
        app_token_row.append(self._app_token_entry)
        box.append(app_token_row)

        name_lbl = Gtk.Label(label="Bot Display Name")
        name_lbl.set_xalign(0)
        name_lbl.set_margin_top(4)
        box.append(name_lbl)
        self._bot_name_entry = Gtk.Entry()
        self._bot_name_entry.set_property("placeholder-text", "Linux Speech Flow")
        box.append(self._bot_name_entry)

        channel_lbl = Gtk.Label(label="Default Channel")
        channel_lbl.set_xalign(0)
        channel_lbl.set_margin_top(4)
        box.append(channel_lbl)
        self._channel_entry = Gtk.Entry()
        self._channel_entry.set_property(
            "placeholder-text", "C1234ABCD \u2014 channel ID, not name"
        )
        box.append(self._channel_entry)

        user_id_lbl = Gtk.Label(label="Your Slack User ID")
        user_id_lbl.set_xalign(0)
        user_id_lbl.set_margin_top(4)
        box.append(user_id_lbl)
        self._slack_user_id_entry = Gtk.Entry()
        self._slack_user_id_entry.set_property(
            "placeholder-text", "U0123ABCD \u2014 from your Slack profile"
        )
        box.append(self._slack_user_id_entry)

        if existing_data:
            self._bot_token_entry.set_text(existing_data.get("bot_token", ""))
            self._app_token_entry.set_text(existing_data.get("app_token", ""))
            self._bot_name_entry.set_text(existing_data.get("bot_name", ""))
            self._channel_entry.set_text(existing_data.get("channel_id", ""))
            self._slack_user_id_entry.set_text(existing_data.get("authed_user_id", ""))

        self._verify_status = Gtk.Label(label="")
        self._verify_status.set_xalign(0)
        self._verify_status.set_wrap(True)
        self._verify_status.add_css_class("error")
        box.append(self._verify_status)

        self._verify_spinner = Gtk.Spinner()
        box.append(self._verify_spinner)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(8)
        btn_row.set_margin_bottom(16)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.destroy())
        btn_row.append(cancel_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_row.append(spacer)

        self._verify_btn = Gtk.Button(label="Verify & Connect")
        self._verify_btn.add_css_class("suggested-action")
        self._verify_btn.connect("clicked", self._on_verify)
        btn_row.append(self._verify_btn)

        outer.append(btn_row)

    def _on_verify(self, _btn):
        bot_token = self._bot_token_entry.get_text().strip()
        app_token = self._app_token_entry.get_text().strip()
        if not bot_token:
            self._set_status(False, "Bot User OAuth Token is required.")
            return
        self._verify_btn.set_sensitive(False)
        self._verify_status.set_text("")
        self._verify_spinner.start()

        bot_name = self._bot_name_entry.get_text().strip() or "Linux Speech Flow"
        channel_id = self._channel_entry.get_text().strip()
        slack_user_id = self._slack_user_id_entry.get_text().strip()

        def run():
            from linux_speech_flow.slack_manager import SlackManager

            manager = SlackManager()
            ok, err = manager.verify_token(bot_token, app_token)
            if ok:
                from slack_sdk import WebClient

                try:
                    client = WebClient(token=bot_token)
                    resp = client.auth_test()
                    team_id = resp.get("team_id", "")
                    team_name = resp.get("team", "")
                    workspace_data = {
                        "bot_token": bot_token,
                        "app_token": app_token,
                        "bot_name": bot_name,
                        "channel_id": channel_id,
                        "authed_user_id": slack_user_id,
                        "team_name": team_name,
                    }
                    manager.add_workspace(team_id, workspace_data)
                    GLib.idle_add(self._on_verify_done, True, "")
                except Exception as exc:
                    GLib.idle_add(self._on_verify_done, False, str(exc))
            else:
                GLib.idle_add(self._on_verify_done, False, err)

        threading.Thread(target=run, daemon=True).start()

    def _on_verify_done(self, ok: bool, err: str):
        self._verify_spinner.stop()
        self._verify_btn.set_sensitive(True)
        if ok:
            self._set_status(True, "Workspace connected successfully.")
            self.emit("workspace-added")
            GLib.timeout_add(800, self.destroy)
        else:
            self._set_status(False, err or "Verification failed.")
        return False

    def _set_status(self, ok: bool, message: str):
        self._verify_status.remove_css_class("error")
        self._verify_status.remove_css_class("success")
        self._verify_status.add_css_class("success" if ok else "error")
        self._verify_status.set_text(message)
