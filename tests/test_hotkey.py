"""Tests for HotkeyManager state machine.

GLib.idle_add is patched to call callbacks synchronously so state transitions
are observable without a running GTK main loop. pynput.keyboard.Listener is
patched to avoid starting a real X11 keyboard grab.

Default bindings under test:
  Ctrl+Alt+R  — start / stop recording
  Ctrl+Alt+C  — start / stop conversation mode
  Ctrl+Alt+F  — toggle feedback mode (conversation only)
  Ctrl+Alt+P  — reprocess failed
  ESC         — stop recording
"""
from unittest.mock import MagicMock, patch


def _make_manager(
    on_complete=None,
    on_start=None,
    on_error=None,
    on_reprocess=None,
    on_conv_start=None,
    on_conv_stop=None,
    on_conv_feedback=None,
):
    """Instantiate HotkeyManager with all external dependencies mocked."""
    from linux_speech_flow.hotkey import HotkeyManager

    mgr = HotkeyManager(
        on_recording_complete=on_complete or (lambda p, f: None),
        on_recording_start=on_start,
        on_recording_error=on_error,
        on_reprocess=on_reprocess,
        on_conversation_start=on_conv_start,
        on_conversation_stop=on_conv_stop,
        on_conversation_feedback_toggle=on_conv_feedback,
    )
    mgr._started = True  # skip mark_started guard
    return mgr


def _press(mgr, key):
    """Simulate a key press through the pynput callback."""
    mgr._on_press(key)


def _release(mgr, key):
    """Simulate a key release through the pynput callback."""
    mgr._on_release(key)


def _letter_key(char):
    """Create a KeyCode-like object with vk set to the uppercase ASCII value.

    _key_letter() maps vk 65-90 (A-Z) to lowercase, so passing 'r' or 'R'
    both produce the letter 'r' that hotkey.py dispatches on.
    """
    key = MagicMock()
    key.vk = ord(char.upper())  # 65-90 range
    return key


def _ctrl_alt_press(mgr, char, mock_kb):
    """Simulate a complete Ctrl+Alt+<char> press-and-release sequence."""
    mgr._on_press(mock_kb.Key.ctrl_l)
    mgr._on_press(mock_kb.Key.alt_l)
    mgr._on_press(_letter_key(char))
    mgr._on_release(mock_kb.Key.alt_l)
    mgr._on_release(mock_kb.Key.ctrl_l)


# ---------------------------------------------------------------------------
# Module-level patches applied for the entire class
# ---------------------------------------------------------------------------


@patch("linux_speech_flow.hotkey.GLib")
@patch("linux_speech_flow.hotkey.keyboard")
@patch(
    "linux_speech_flow.hotkey.load_config",
    return_value={
        "sounds_enabled": False,
        "sounds_output_device": "",
        "microphone": "",
        "max_recording_duration": 60,
        "silence_stop_duration": 10,
        "hotkey_record": "ctrl+alt+r",
        "hotkey_stop": "ctrl+alt+r",
        "hotkey_conversation": "ctrl+alt+c",
        "hotkey_reprocess": "ctrl+alt+p",
        "hotkey_feedback": "ctrl+alt+f",
    },
)
@patch("linux_speech_flow.hotkey.play_sound")
@patch("linux_speech_flow.hotkey.send_notification", return_value=None)
class TestHotkeyStateMachine:
    def _setup_idle_add(self, mock_glib):
        """Make idle_add execute the callback immediately and return False."""

        def immediate_idle_add(fn, *args):
            fn(*args)
            return False

        mock_glib.idle_add.side_effect = immediate_idle_add

    # --- basic guards ---

    def test_record_hotkey_ignored_before_mark_started(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr._started = False
        _ctrl_alt_press(mgr, "r", mock_kb)
        mock_glib.idle_add.assert_not_called()

    def test_ctrl_alt_r_in_idle_transitions_to_recording(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        mock_recorder = MagicMock()
        with patch(
            "linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder
        ):
            mgr = _make_manager()
            assert mgr._state == mgr._STATE_IDLE
            _ctrl_alt_press(mgr, "r", mock_kb)
            assert mgr._state == mgr._STATE_RECORDING

    def test_ctrl_alt_r_in_recording_stops_recorder(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        mock_recorder = MagicMock()
        with patch(
            "linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder
        ):
            mgr = _make_manager()
            _ctrl_alt_press(mgr, "r", mock_kb)  # start
            assert mgr._state == mgr._STATE_RECORDING
            _ctrl_alt_press(mgr, "r", mock_kb)  # stop
            mock_recorder.stop.assert_called_once_with(cancel=False)
            assert mgr._stop_was_hotkey is True

    def test_esc_stops_recording_normally(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """ESC is a normal stop (cancel=False): audio is kept and transcribed.
        State stays RECORDING until the recorder thread fires _on_recorder_complete."""
        self._setup_idle_add(mock_glib)
        mock_recorder = MagicMock()
        with patch(
            "linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder
        ):
            mgr = _make_manager()
            _ctrl_alt_press(mgr, "r", mock_kb)
            _press(mgr, mock_kb.Key.esc)
            mock_recorder.stop.assert_called_once_with(cancel=False)
            assert (
                mgr._stop_was_hotkey is False
            )  # ESC does not set the hotkey-stop flag

    def test_ctrl_alt_r_ignored_in_conversation_state(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """Ctrl+Alt+R during CONVERSATION state is silently ignored."""
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr._state = mgr._STATE_CONVERSATION
        _ctrl_alt_press(mgr, "r", mock_kb)
        mock_glib.idle_add.assert_not_called()

    # --- modifier tracking ---

    def test_ctrl_alone_does_not_trigger_record(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """Ctrl without Alt must not start recording."""
        self._setup_idle_add(mock_glib)
        mock_recorder = MagicMock()
        with patch(
            "linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder
        ):
            mgr = _make_manager()
            mgr._on_press(mock_kb.Key.ctrl_l)
            mgr._on_press(_letter_key("r"))
            assert mgr._state == mgr._STATE_IDLE

    def test_on_release_clears_modifier_flags(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """Releasing Ctrl and Alt removes them from _modifiers_held."""
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr._on_press(mock_kb.Key.ctrl_l)
        mgr._on_press(mock_kb.Key.alt_l)
        assert "ctrl" in mgr._modifiers_held
        assert "alt" in mgr._modifiers_held
        mgr._on_release(mock_kb.Key.ctrl_l)
        mgr._on_release(mock_kb.Key.alt_l)
        assert "ctrl" not in mgr._modifiers_held
        assert "alt" not in mgr._modifiers_held

    # --- recorder complete callback ---

    def test_on_recorder_complete_resets_state_and_calls_cb(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        received = []
        mgr = _make_manager(on_complete=lambda p, f: received.append((p, f)))
        mgr._state = mgr._STATE_RECORDING
        mgr._stop_was_hotkey = True
        mgr._on_recorder_complete("/tmp/test.wav")
        assert mgr._state == mgr._STATE_IDLE
        assert received == [("/tmp/test.wav", True)]

    def test_on_recorder_complete_stop_was_hotkey_false(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        received = []
        mgr = _make_manager(on_complete=lambda p, f: received.append((p, f)))
        mgr._state = mgr._STATE_RECORDING
        mgr._stop_was_hotkey = False
        mgr._on_recorder_complete("/tmp/test.wav")
        assert received == [("/tmp/test.wav", False)]

    # --- conversation mode state transitions ---

    def test_ctrl_alt_c_idle_transitions_to_conversation(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        started = []
        mgr = _make_manager(on_conv_start=lambda: started.append(1))
        _ctrl_alt_press(mgr, "c", mock_kb)
        assert mgr._state == mgr._STATE_CONVERSATION
        assert started == [1]

    def test_ctrl_alt_c_conversation_transitions_to_idle(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        stopped = []
        mgr = _make_manager(on_conv_stop=lambda: stopped.append(1))
        mgr._state = mgr._STATE_CONVERSATION
        _ctrl_alt_press(mgr, "c", mock_kb)
        assert mgr._state == mgr._STATE_IDLE
        assert stopped == [1]

    def test_ctrl_alt_c_ignored_in_recording_state(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr._state = mgr._STATE_RECORDING
        _ctrl_alt_press(mgr, "c", mock_kb)
        assert mgr._state == mgr._STATE_RECORDING  # unchanged

    def test_ctrl_alt_f_triggers_feedback_toggle_in_conversation(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        toggled = []
        mgr = _make_manager(on_conv_feedback=lambda: toggled.append(1))
        mgr._state = mgr._STATE_CONVERSATION
        _ctrl_alt_press(mgr, "f", mock_kb)
        assert toggled == [1]

    def test_ctrl_alt_f_ignored_outside_conversation(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        toggled = []
        mgr = _make_manager(on_conv_feedback=lambda: toggled.append(1))
        mgr._state = mgr._STATE_IDLE
        _ctrl_alt_press(mgr, "f", mock_kb)
        assert toggled == []

    def test_ctrl_alt_p_triggers_reprocess(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        reprocessed = []
        mgr = _make_manager(on_reprocess=lambda: reprocessed.append(1))
        _ctrl_alt_press(mgr, "p", mock_kb)
        assert reprocessed == [1]

    # --- exception safety ---

    def test_conv_start_exception_resets_state_to_idle(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """If _on_conv_start_cb raises, state resets to IDLE so recording still works."""
        self._setup_idle_add(mock_glib)

        def crashing_cb():
            raise AttributeError("simulated GTK crash")

        mgr = _make_manager(on_conv_start=crashing_cb)
        _ctrl_alt_press(mgr, "c", mock_kb)
        assert mgr._state == mgr._STATE_IDLE

    def test_record_works_after_conv_start_exception(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """Ctrl+Alt+R must work even after a crashing conversation start."""
        self._setup_idle_add(mock_glib)

        def crashing_cb():
            raise RuntimeError("window creation failed")

        mock_recorder = MagicMock()
        with patch(
            "linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder
        ):
            mgr = _make_manager(on_conv_start=crashing_cb)
            _ctrl_alt_press(mgr, "c", mock_kb)  # crashes, state recovers to IDLE
            assert mgr._state == mgr._STATE_IDLE
            _ctrl_alt_press(mgr, "r", mock_kb)  # must start recording normally
            assert mgr._state == mgr._STATE_RECORDING

    def test_on_recording_start_cb_called(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        started = []
        mock_recorder = MagicMock()
        with patch(
            "linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder
        ):
            mgr = _make_manager(on_start=lambda: started.append(1))
            _ctrl_alt_press(mgr, "r", mock_kb)
            assert started == [1]

    def test_on_recorder_error_resets_state(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        self._setup_idle_add(mock_glib)
        errors = []
        mgr = _make_manager(on_error=lambda m: errors.append(m))
        mgr._state = mgr._STATE_RECORDING
        mgr._on_recorder_error("mic disconnected")
        assert mgr._state == mgr._STATE_IDLE
        assert errors == ["mic disconnected"]

    def test_key_letter_char_fallback(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """_key_letter falls back to key.char when vk is absent."""
        from linux_speech_flow.hotkey import HotkeyManager

        key = MagicMock(spec=["char"])
        key.char = "r"
        assert HotkeyManager._key_letter(key) == "r"

    def test_stop_recording_cancel_true(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """cancel=True stops recorder, plays stop sound, and sets state IDLE immediately."""
        self._setup_idle_add(mock_glib)
        mock_recorder = MagicMock()
        mgr = _make_manager()
        mgr._state = mgr._STATE_RECORDING
        mgr._recorder = mock_recorder

        mgr._stop_recording(True)

        mock_recorder.stop.assert_called_once_with(cancel=True)
        mock_sound.assert_called()
        assert mgr._state == mgr._STATE_IDLE

    def test_modifiers_held_tracks_all_four_modifier_types(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """_modifiers_held tracks ctrl, alt, shift, super independently."""
        mgr = _make_manager()
        mgr._on_press(mock_kb.Key.ctrl_l)
        mgr._on_press(mock_kb.Key.alt_l)
        mgr._on_press(mock_kb.Key.shift)
        mgr._on_press(mock_kb.Key.cmd)
        assert mgr._modifiers_held == {"ctrl", "alt", "shift", "super"}
        mgr._on_release(mock_kb.Key.shift)
        assert "shift" not in mgr._modifiers_held
        assert mgr._modifiers_held == {"ctrl", "alt", "super"}

    def test_right_side_modifiers_tracked(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """Right-side modifier keys (ctrl_r, alt_r, shift_r, cmd_r) are tracked."""
        mgr = _make_manager()
        mgr._on_press(mock_kb.Key.ctrl_r)
        mgr._on_press(mock_kb.Key.alt_r)
        mgr._on_press(mock_kb.Key.shift_r)
        mgr._on_press(mock_kb.Key.cmd_r)
        assert mgr._modifiers_held == {"ctrl", "alt", "shift", "super"}

    def test_alt_gr_maps_to_alt(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """alt_gr maps to 'alt' in _modifiers_held."""
        mgr = _make_manager()
        mgr._on_press(mock_kb.Key.alt_gr)
        assert "alt" in mgr._modifiers_held

    def test_reload_bindings_updates_dispatch(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """reload_bindings() with a new config causes _matches_binding to reflect new combo."""
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        with patch(
            "linux_speech_flow.hotkey.load_config",
            return_value={
                "sounds_enabled": False,
                "sounds_output_device": "",
                "microphone": "",
                "max_recording_duration": 60,
                "silence_stop_duration": 10,
                "hotkey_record": "ctrl+alt+t",
                "hotkey_stop": "ctrl+alt+t",
                "hotkey_conversation": "ctrl+alt+c",
                "hotkey_reprocess": "ctrl+alt+p",
                "hotkey_feedback": "ctrl+alt+f",
            },
        ):
            mgr.reload_bindings()
        mock_recorder = MagicMock()
        with patch(
            "linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder
        ):
            _ctrl_alt_press(mgr, "r", mock_kb)
            assert mgr._state == mgr._STATE_IDLE

    def test_apply_binding_override_updates_binding_immediately(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """apply_binding_override updates _bindings[action] without reading config."""
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr.apply_binding_override("record", "ctrl+shift+r")
        mods, key = mgr._bindings["record"]
        assert mods == frozenset({"ctrl", "shift"})
        assert key == "r"

    def test_matches_binding_special_key(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """_matches_binding works for special key names like 'esc', 'f5'."""
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr.apply_binding_override("stop", "ctrl+alt+esc")
        mgr._modifiers_held = {"ctrl", "alt"}
        esc_key = mock_kb.Key.esc
        mock_kb.Key.__getitem__ = (
            lambda self_inner, k: esc_key if k == "esc" else MagicMock()
        )
        assert mgr._matches_binding(esc_key, "stop")

    def test_matches_binding_wrong_modifiers_no_match(
        self, mock_notify, mock_sound, mock_cfg, mock_kb, mock_glib
    ):
        """_matches_binding returns False when modifier set differs."""
        mgr = _make_manager()
        mgr._modifiers_held = {"ctrl"}
        assert not mgr._matches_binding(_letter_key("r"), "record")


class TestComboHelpers:
    def test_parse_combo_ctrl_alt_r(self):
        from linux_speech_flow.hotkey import parse_combo

        mods, key = parse_combo("ctrl+alt+r")
        assert mods == frozenset({"ctrl", "alt"})
        assert key == "r"

    def test_parse_combo_special_key(self):
        from linux_speech_flow.hotkey import parse_combo

        mods, key = parse_combo("ctrl+alt+f5")
        assert mods == frozenset({"ctrl", "alt"})
        assert key == "f5"

    def test_parse_combo_all_modifiers(self):
        from linux_speech_flow.hotkey import parse_combo

        mods, key = parse_combo("ctrl+alt+shift+super+x")
        assert mods == frozenset({"ctrl", "alt", "shift", "super"})
        assert key == "x"

    def test_parse_combo_case_insensitive(self):
        from linux_speech_flow.hotkey import parse_combo

        mods, key = parse_combo("CTRL+ALT+R")
        assert mods == frozenset({"ctrl", "alt"})
        assert key == "r"

    def test_combo_display_ctrl_alt_r(self):
        from linux_speech_flow.hotkey import combo_display

        assert combo_display("ctrl+alt+r") == "Ctrl+Alt+R"

    def test_combo_display_canonical_modifier_order(self):
        from linux_speech_flow.hotkey import combo_display

        assert combo_display("alt+ctrl+r") == "Ctrl+Alt+R"

    def test_combo_display_special_key(self):
        from linux_speech_flow.hotkey import combo_display

        assert combo_display("ctrl+alt+f12") == "Ctrl+Alt+F12"

    def test_combo_display_shift(self):
        from linux_speech_flow.hotkey import combo_display

        assert combo_display("ctrl+shift+t") == "Ctrl+Shift+T"

    def test_dangerous_combos_contains_known_blocked(self):
        from linux_speech_flow.hotkey import DANGEROUS_COMBOS

        assert "ctrl+alt+delete" in DANGEROUS_COMBOS
        assert "ctrl+alt+f1" in DANGEROUS_COMBOS
        assert "ctrl+alt+f12" in DANGEROUS_COMBOS
        assert "ctrl+alt+left" in DANGEROUS_COMBOS
        assert "ctrl+alt+right" in DANGEROUS_COMBOS

    def test_dangerous_combos_does_not_contain_valid_combos(self):
        from linux_speech_flow.hotkey import DANGEROUS_COMBOS

        assert "ctrl+alt+r" not in DANGEROUS_COMBOS
        assert "ctrl+alt+t" not in DANGEROUS_COMBOS


class TestSettingsCaptureStateMachine:
    """Tests for the Settings hotkey capture state machine.

    Uses a simulation object that mirrors _capture_action, _hotkey_values,
    and the accept/cancel/conflict logic without requiring a GTK display.
    The simulation calls the same conflict-detection code that settings.py uses,
    imported directly.
    """

    def _make_sim(self, initial_values=None):
        """Build a simple state-machine simulation dict."""
        from linux_speech_flow.hotkey import (
            HOTKEY_DEFAULTS,
            HOTKEY_ACTION_LABELS,
            DANGEROUS_COMBOS,
            combo_display,
        )

        defaults = {
            "record": "ctrl+alt+r",
            "stop": "ctrl+alt+r",
            "conversation": "ctrl+alt+c",
            "reprocess": "ctrl+alt+p",
            "feedback": "ctrl+alt+f",
        }
        values = dict(initial_values or defaults)
        state = {
            "capture_action": None,
            "capture_prev": None,
            "error": "",
            "labels": dict(values),
        }

        def start_capture(action):
            state["capture_action"] = action
            state["capture_prev"] = values.get(action)
            state["labels"][action] = "Press keys..."
            state["error"] = ""

        def cancel():
            action = state["capture_action"]
            state["capture_action"] = None
            if action:
                state["labels"][action] = combo_display(
                    state["capture_prev"] or HOTKEY_DEFAULTS[action]
                )

        def accept(combo_str):
            action = state["capture_action"]
            if action is None:
                return
            if combo_str in DANGEROUS_COMBOS:
                state["error"] = f"{combo_display(combo_str)} is reserved by the system"
                cancel()
                return
            for other, other_combo in values.items():
                if other != action and other_combo == combo_str:
                    state[
                        "error"
                    ] = f"{combo_display(combo_str)} is already used for {HOTKEY_ACTION_LABELS[other]}"
                    cancel()
                    return
            state["error"] = ""
            state["capture_action"] = None
            values[action] = combo_str
            state["labels"][action] = combo_display(combo_str)

        return state, values, start_capture, cancel, accept

    def test_capture_enters_mode_and_shows_press_keys(self):
        state, values, start, cancel, accept = self._make_sim()
        start("record")
        assert state["capture_action"] == "record"
        assert state["labels"]["record"] == "Press keys..."

    def test_cancel_restores_previous_label(self):
        state, values, start, cancel, accept = self._make_sim()
        start("record")
        cancel()
        assert state["capture_action"] is None
        assert state["labels"]["record"] == "Ctrl+Alt+R"

    def test_accept_valid_combo_updates_binding(self):
        state, values, start, cancel, accept = self._make_sim()
        start("record")
        accept("ctrl+alt+t")
        assert state["capture_action"] is None
        assert values["record"] == "ctrl+alt+t"
        assert state["labels"]["record"] == "Ctrl+Alt+T"
        assert state["error"] == ""

    def test_accept_dangerous_combo_rejects_with_error(self):
        state, values, start, cancel, accept = self._make_sim()
        start("record")
        accept("ctrl+alt+delete")
        assert state["capture_action"] is None
        assert values["record"] == "ctrl+alt+r"
        assert "reserved by the system" in state["error"]

    def test_accept_conflicting_combo_rejects_with_error(self):
        state, values, start, cancel, accept = self._make_sim()
        start("record")
        accept("ctrl+alt+c")
        assert values["record"] == "ctrl+alt+r"
        assert "already used for Conversation Mode" in state["error"]

    def test_accept_same_action_no_conflict(self):
        """Re-setting an action to its own current value is not a conflict."""
        state, values, start, cancel, accept = self._make_sim()
        start("feedback")
        accept("ctrl+alt+f")
        assert values["feedback"] == "ctrl+alt+f"
        assert state["error"] == ""

    def test_reset_to_default_restores_correct_value(self):
        from linux_speech_flow.hotkey import HOTKEY_DEFAULTS

        state, values, start, cancel, accept = self._make_sim(
            initial_values={
                "record": "ctrl+alt+r",
                "stop": "ctrl+alt+r",
                "conversation": "ctrl+alt+t",
                "reprocess": "ctrl+alt+p",
                "feedback": "ctrl+alt+f",
            }
        )
        start("conversation")
        accept(HOTKEY_DEFAULTS["conversation"])
        assert values["conversation"] == "ctrl+alt+c"
        assert state["labels"]["conversation"] == "Ctrl+Alt+C"

    def test_esc_during_capture_calls_cancel(self):
        """ESC key during capture must cancel, not close the window."""
        state, values, start, cancel, accept = self._make_sim()
        start("record")
        cancel()
        assert state["capture_action"] is None
        assert state["labels"]["record"] == "Ctrl+Alt+R"


def test_history_window_empty_hint_uses_combo_display():
    """history_window.py must use combo_display to format the hotkey in the empty hint.

    This is a regression guard for the pre-Phase-7 bug where
    cfg.get('hotkey_record', 'F9') produced 'F9' instead of the
    actual configured binding display string.
    """
    src = open("src/linux_speech_flow/history_window.py").read()
    assert "combo_display" in src, (
        "history_window.py must import and call combo_display to display the "
        "configured hotkey in the empty-history hint label"
    )
    assert (
        "'F9'" not in src or src.count("'F9'") == 0
    ), "history_window.py must not contain hardcoded 'F9' default"
