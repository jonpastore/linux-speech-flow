import math
import struct
import subprocess
import threading
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, Pango

LLM_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

from linux_speech_flow.audio import list_microphones
from linux_speech_flow.config import load_config, save_config
from linux_speech_flow.groq_client import validate_api_key
from linux_speech_flow.history import HistoryStore, DB_PATH
from linux_speech_flow.transcription import FAILED_DIR

import pulsectl


def _block_scroll(combo: Gtk.ComboBoxText) -> None:
    ctrl = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
    ctrl.connect("scroll", lambda _c, _dx, _dy: True)
    combo.add_controller(ctrl)


def _block_scroll_spin(spin: Gtk.SpinButton) -> None:
    ctrl = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
    ctrl.connect("scroll", lambda _c, _dx, _dy: True)
    spin.add_controller(ctrl)


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Settings")
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
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

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

        api_title = Gtk.Label(label="AI Integrations")
        api_title.add_css_class("title-4")
        api_title.set_xalign(0)
        content.append(api_title)

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
        _attrs2.insert(Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold")))
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
        _attrs3.insert(Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold")))
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

        sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep1.set_margin_top(8)
        sep1.set_margin_bottom(8)
        content.append(sep1)

        vocab_title = Gtk.Label(label="Vocabulary (optional)")
        vocab_title.add_css_class("title-4")
        vocab_title.set_xalign(0)
        content.append(vocab_title)

        vocab_desc = Gtk.Label(label="Enter custom words or phrases, one per line. Leave empty to skip.")
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

        vu_hint = Gtk.Label(label="Speak to confirm your microphone is picking up audio.")
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
        self._max_duration_spin.set_value(self._config.get("max_recording_duration", 300))
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
        self._proc_path_label = Gtk.Label(label=proc_path_val if proc_path_val else "Bundled default")
        self._proc_path_label.set_xalign(0)
        self._proc_path_label.add_css_class("dim-label")
        self._proc_path_label.set_ellipsize(Pango.EllipsizeMode.START)

        proc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        processing_label = Gtk.Label(label="Processing sound")
        processing_label.set_hexpand(True)
        processing_label.set_xalign(0)
        proc_play_btn = Gtk.Button(label="▶")
        proc_play_btn.set_tooltip_text("Preview sound")
        proc_play_btn.connect("clicked", self._on_play_sound, "processing.wav", "processing_sound_file")
        proc_choose_btn = Gtk.Button(label="Choose file")
        proc_choose_btn.connect("clicked", self._on_choose_sound, "processing_sound_file", self._proc_path_label)
        self._processing_sound_switch = Gtk.Switch()
        self._processing_sound_switch.set_active(self._config.get("processing_sound_enabled", True))
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
        self._success_path_label = Gtk.Label(label=success_path_val if success_path_val else "Bundled default")
        self._success_path_label.set_xalign(0)
        self._success_path_label.add_css_class("dim-label")
        self._success_path_label.set_ellipsize(Pango.EllipsizeMode.START)

        success_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        success_label = Gtk.Label(label="Success chime")
        success_label.set_hexpand(True)
        success_label.set_xalign(0)
        success_play_btn = Gtk.Button(label="▶")
        success_play_btn.set_tooltip_text("Preview sound")
        success_play_btn.connect("clicked", self._on_play_sound, "success.wav", "success_sound_file")
        success_choose_btn = Gtk.Button(label="Choose file")
        success_choose_btn.connect("clicked", self._on_choose_sound, "success_sound_file", self._success_path_label)
        self._success_sound_switch = Gtk.Switch()
        self._success_sound_switch.set_active(self._config.get("success_sound_enabled", True))
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
        attrs_bold.insert(Pango.AttrFontDesc.new(Pango.FontDescription.from_string("bold")))
        history_header.set_attributes(attrs_bold)
        history_header.set_xalign(0)
        history_header.set_margin_top(4)
        content.append(history_header)

        max_entries_label = Gtk.Label(label="Max entries to keep")
        max_entries_label.set_xalign(0)
        content.append(max_entries_label)

        self._history_max_entries_spin = Gtk.SpinButton.new_with_range(5, 500, 1)
        self._history_max_entries_spin.set_value(self._config.get('history_max_entries', 20))
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

        advanced_expander = Gtk.Expander(label="Advanced — changing the prompt may break post-processing")
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

        self._prompt_view.get_buffer().set_text(self._config.get("llm_system_prompt", ""))

        reset_btn = Gtk.Button(label="Reset to Default")
        reset_btn.connect("clicked", self._on_reset_prompt)
        advanced_box.append(reset_btn)

        sep_conv = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep_conv.set_margin_top(8)
        sep_conv.set_margin_bottom(8)
        content.append(sep_conv)

        conv_title = Gtk.Label(label="Conversation Mode")
        conv_title.add_css_class("title-4")
        conv_title.set_xalign(0)
        content.append(conv_title)

        mic_sens_label = Gtk.Label(label="Mic Sensitivity")
        mic_sens_label.set_xalign(0)
        content.append(mic_sens_label)

        conv_vu_overlay = Gtk.Overlay()
        self._conv_vu_bar = Gtk.LevelBar()
        self._conv_vu_bar.set_min_value(0.0)
        self._conv_vu_bar.set_max_value(1.0)
        self._conv_vu_bar.set_value(0.0)
        conv_vu_overlay.set_child(self._conv_vu_bar)

        self._conv_threshold_area = Gtk.DrawingArea()
        self._conv_threshold_area.set_can_target(False)
        self._conv_threshold_area.set_draw_func(self._draw_conv_threshold, None)
        conv_vu_overlay.add_overlay(self._conv_threshold_area)

        content.append(conv_vu_overlay)

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
        self._conv_threshold_scale.connect("value-changed", self._on_conv_threshold_changed)
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
        self._conv_warn_spin.set_value(
            self._config.get("conv_silence_warn_sec", 30)
        )
        content.append(self._conv_warn_spin)

        stop_label = Gtk.Label(label="Silence auto-stop timeout (seconds)")
        stop_label.set_xalign(0)
        content.append(stop_label)
        stop_hint = Gtk.Label(label="Auto-stops if you ignore the prompt. Must be > prompt timeout.")
        stop_hint.set_xalign(0)
        stop_hint.set_wrap(True)
        stop_hint.add_css_class("dim-label")
        content.append(stop_hint)
        self._conv_stop_spin = Gtk.SpinButton.new_with_range(10, 600, 5)
        _block_scroll_spin(self._conv_stop_spin)
        self._conv_stop_spin.set_value(
            self._config.get("conv_silence_stop_sec", 60)
        )
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

        qa_label = Gtk.Label(label="Max Q&A Rounds (before 'continue?' prompt)")
        qa_label.set_xalign(0)
        content.append(qa_label)
        self._qa_spin = Gtk.SpinButton()
        _block_scroll_spin(self._qa_spin)
        self._qa_spin.configure(
            Gtk.Adjustment.new(
                self._config.get("conv_max_qa_iterations", 3), 1, 20, 1, 1, 0
            ), 1, 0
        )
        content.append(self._qa_spin)

        self._auto_analyze_check = Gtk.CheckButton(
            label="Auto-enable AI analysis in post-stop dialog"
        )
        self._auto_analyze_check.set_active(
            self._config.get("conv_auto_analyze", True)
        )
        content.append(self._auto_analyze_check)

        conv_prompt_label = Gtk.Label(label="Default Analysis Prompt")
        conv_prompt_label.set_xalign(0)
        content.append(conv_prompt_label)
        conv_prompt_scroll = Gtk.ScrolledWindow()
        conv_prompt_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        conv_prompt_scroll.set_min_content_height(80)
        conv_prompt_scroll.set_max_content_height(120)
        self._conv_prompt_buf = Gtk.TextBuffer()
        self._conv_prompt_buf.set_text(
            self._config.get("conv_default_prompt", "")
        )
        conv_prompt_tv = Gtk.TextView(buffer=self._conv_prompt_buf)
        conv_prompt_tv.set_wrap_mode(Gtk.WrapMode.WORD)
        conv_prompt_scroll.set_child(conv_prompt_tv)
        content.append(conv_prompt_scroll)

        qq_label = Gtk.Label(label="Qualifying Questions (one per line)")
        qq_label.set_xalign(0)
        content.append(qq_label)
        qq_sub = Gtk.Label(label="Shown in the post-stop dialog to help calibrate AI response complexity")
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
        self._conv_qq_buf.set_text("\n".join(existing_qq) if isinstance(existing_qq, list) else existing_qq)
        qq_tv = Gtk.TextView(buffer=self._conv_qq_buf)
        qq_tv.set_wrap_mode(Gtk.WrapMode.WORD)
        qq_scroll.set_child(qq_tv)
        content.append(qq_scroll)

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
            "parec", "--raw", "--channels=1", "--format=s16le",
            f"--rate={RATE}", "--latency-msec=50", "-d", source_name,
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
        self._conv_vu_bar.set_value(level)
        return False

    def _draw_conv_threshold(self, area, cr, width, height, _data) -> None:
        from linux_speech_flow.conversation_recorder import RMS_DISPLAY_SCALE
        normalized = min(1.0, self._conv_threshold_scale.get_value() * RMS_DISPLAY_SCALE)
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

    def _on_conv_threshold_changed(self, _scale) -> None:
        self._conv_threshold_area.queue_draw()
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
            self._set_status(self._groq_status, False, result.get("message", "Validation failed"))
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
                GLib.idle_add(self._on_test_grok_done, {"ok": False, "message": str(exc)})
            return False

        threading.Thread(target=run, daemon=True).start()

    def _on_test_grok_done(self, result: dict):
        self._grok_spinner.stop()
        self._grok_test_btn.set_sensitive(True)
        if result["ok"]:
            self._set_status(self._grok_status, True, "API key is valid.")
        else:
            self._set_status(self._grok_status, False, result.get("message", "Test failed"))
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
                GLib.idle_add(self._on_test_gemini_done, {"ok": False, "message": str(exc)})
            return False

        threading.Thread(target=run, daemon=True).start()

    def _on_test_gemini_done(self, result: dict):
        self._gemini_spinner.stop()
        self._gemini_test_btn.set_sensitive(True)
        if result["ok"]:
            self._set_status(self._gemini_status, True, "API key is valid.")
        else:
            self._set_status(self._gemini_status, False, result.get("message", "Test failed"))
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
        config["llm_model"] = self._llm_model_list[self._llm_model_dropdown.get_selected()]
        config["pipeline_timeout"] = int(self._pipeline_timeout_spin.get_value())
        config["processing_sound_enabled"] = self._processing_sound_switch.get_active()
        config["processing_sound_file"] = self._config.get("processing_sound_file", "")
        config["success_sound_enabled"] = self._success_sound_switch.get_active()
        config["success_sound_file"] = self._config.get("success_sound_file", "")
        config["history_max_entries"] = int(self._history_max_entries_spin.get_value())
        config["grok_api_key"] = self._grok_key_entry.get_text().strip()
        config["gemini_api_key"] = self._gemini_key_entry.get_text().strip()
        config["conv_silence_rms_threshold"] = self._conv_threshold_scale.get_value()
        config["conv_silence_warn_sec"] = int(self._conv_warn_spin.get_value())
        config["conv_silence_stop_sec"] = int(self._conv_stop_spin.get_value())
        config["conv_save_dir"] = self._conv_save_entry.get_text().strip()
        config["conv_feedback_mode"] = self._feedback_combo.get_active_id() or "status_window"
        config["conv_max_qa_iterations"] = int(self._qa_spin.get_value())
        config["conv_auto_analyze"] = self._auto_analyze_check.get_active()
        config["conv_default_prompt"] = self._conv_prompt_buf.get_text(
            self._conv_prompt_buf.get_start_iter(),
            self._conv_prompt_buf.get_end_iter(), False
        )
        _qq_raw = self._conv_qq_buf.get_text(
            self._conv_qq_buf.get_start_iter(),
            self._conv_qq_buf.get_end_iter(), False
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

    def _on_sound_chosen(self, dialog, response, config_key: str, path_label: Gtk.Label):
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
        self._conv_warn_spin.connect("value-changed", md)
        self._conv_stop_spin.connect("value-changed", md)
        self._conv_save_entry.connect("changed", md)
        self._feedback_combo.connect("changed", md)
        self._qa_spin.connect("value-changed", md)
        self._auto_analyze_check.connect("toggled", md)
        self._conv_prompt_buf.connect("changed", md)
        self._conv_qq_buf.connect("changed", md)

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
        self._maint_status_label.set_label(f"Temp audio files cleared ({count} removed).")

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

    def _on_key_pressed(self, _ctrl, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_close(self, _window):
        if self._closing:
            self._stop_vu_meter()
            return False
        if self._is_dirty():
            self._show_unsaved_dialog()
            return True
        self._stop_vu_meter()
        return False
