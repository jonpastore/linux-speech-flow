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


def _make_manager(on_complete=None, on_start=None, on_error=None,
                  on_reprocess=None, on_conv_start=None, on_conv_stop=None,
                  on_conv_feedback=None):
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
@patch("linux_speech_flow.hotkey.load_config", return_value={
    "sounds_enabled": False,
    "sounds_output_device": "",
    "microphone": "",
    "max_recording_duration": 60,
    "silence_stop_duration": 10,
})
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

    def test_record_hotkey_ignored_before_mark_started(self, mock_notify, mock_sound,
                                                        mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr._started = False
        _ctrl_alt_press(mgr, 'r', mock_kb)
        mock_glib.idle_add.assert_not_called()

    def test_ctrl_alt_r_in_idle_transitions_to_recording(self, mock_notify, mock_sound,
                                                           mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager()
            assert mgr._state == mgr._STATE_IDLE
            _ctrl_alt_press(mgr, 'r', mock_kb)
            assert mgr._state == mgr._STATE_RECORDING

    def test_ctrl_alt_r_in_recording_stops_recorder(self, mock_notify, mock_sound,
                                                      mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager()
            _ctrl_alt_press(mgr, 'r', mock_kb)  # start
            assert mgr._state == mgr._STATE_RECORDING
            _ctrl_alt_press(mgr, 'r', mock_kb)  # stop
            mock_recorder.stop.assert_called_once_with(cancel=False)
            assert mgr._stop_was_hotkey is True

    def test_esc_stops_recording_normally(self, mock_notify, mock_sound,
                                          mock_cfg, mock_kb, mock_glib):
        """ESC is a normal stop (cancel=False): audio is kept and transcribed.
        State stays RECORDING until the recorder thread fires _on_recorder_complete."""
        self._setup_idle_add(mock_glib)
        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager()
            _ctrl_alt_press(mgr, 'r', mock_kb)
            _press(mgr, mock_kb.Key.esc)
            mock_recorder.stop.assert_called_once_with(cancel=False)
            assert mgr._stop_was_hotkey is False  # ESC does not set the hotkey-stop flag

    def test_ctrl_alt_r_ignored_in_conversation_state(self, mock_notify, mock_sound,
                                                        mock_cfg, mock_kb, mock_glib):
        """Ctrl+Alt+R during CONVERSATION state is silently ignored."""
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr._state = mgr._STATE_CONVERSATION
        _ctrl_alt_press(mgr, 'r', mock_kb)
        mock_glib.idle_add.assert_not_called()

    # --- modifier tracking ---

    def test_ctrl_alone_does_not_trigger_record(self, mock_notify, mock_sound,
                                                 mock_cfg, mock_kb, mock_glib):
        """Ctrl without Alt must not start recording."""
        self._setup_idle_add(mock_glib)
        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager()
            mgr._on_press(mock_kb.Key.ctrl_l)
            mgr._on_press(_letter_key('r'))
            assert mgr._state == mgr._STATE_IDLE

    def test_on_release_clears_modifier_flags(self, mock_notify, mock_sound,
                                               mock_cfg, mock_kb, mock_glib):
        """Releasing Ctrl and Alt clears the held-modifier flags."""
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr._on_press(mock_kb.Key.ctrl_l)
        mgr._on_press(mock_kb.Key.alt_l)
        assert mgr._ctrl_held is True
        assert mgr._alt_held is True
        mgr._on_release(mock_kb.Key.ctrl_l)
        mgr._on_release(mock_kb.Key.alt_l)
        assert mgr._ctrl_held is False
        assert mgr._alt_held is False

    # --- recorder complete callback ---

    def test_on_recorder_complete_resets_state_and_calls_cb(self, mock_notify,
                                                              mock_sound, mock_cfg,
                                                              mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        received = []
        mgr = _make_manager(on_complete=lambda p, f: received.append((p, f)))
        mgr._state = mgr._STATE_RECORDING
        mgr._stop_was_hotkey = True
        mgr._on_recorder_complete("/tmp/test.wav")
        assert mgr._state == mgr._STATE_IDLE
        assert received == [("/tmp/test.wav", True)]

    def test_on_recorder_complete_stop_was_hotkey_false(self, mock_notify, mock_sound,
                                                          mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        received = []
        mgr = _make_manager(on_complete=lambda p, f: received.append((p, f)))
        mgr._state = mgr._STATE_RECORDING
        mgr._stop_was_hotkey = False
        mgr._on_recorder_complete("/tmp/test.wav")
        assert received == [("/tmp/test.wav", False)]

    # --- conversation mode state transitions ---

    def test_ctrl_alt_c_idle_transitions_to_conversation(self, mock_notify, mock_sound,
                                                           mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        started = []
        mgr = _make_manager(on_conv_start=lambda: started.append(1))
        _ctrl_alt_press(mgr, 'c', mock_kb)
        assert mgr._state == mgr._STATE_CONVERSATION
        assert started == [1]

    def test_ctrl_alt_c_conversation_transitions_to_idle(self, mock_notify, mock_sound,
                                                           mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        stopped = []
        mgr = _make_manager(on_conv_stop=lambda: stopped.append(1))
        mgr._state = mgr._STATE_CONVERSATION
        _ctrl_alt_press(mgr, 'c', mock_kb)
        assert mgr._state == mgr._STATE_IDLE
        assert stopped == [1]

    def test_ctrl_alt_c_ignored_in_recording_state(self, mock_notify, mock_sound,
                                                     mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr._state = mgr._STATE_RECORDING
        _ctrl_alt_press(mgr, 'c', mock_kb)
        assert mgr._state == mgr._STATE_RECORDING  # unchanged

    def test_ctrl_alt_f_triggers_feedback_toggle_in_conversation(self, mock_notify,
                                                                   mock_sound, mock_cfg,
                                                                   mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        toggled = []
        mgr = _make_manager(on_conv_feedback=lambda: toggled.append(1))
        mgr._state = mgr._STATE_CONVERSATION
        _ctrl_alt_press(mgr, 'f', mock_kb)
        assert toggled == [1]

    def test_ctrl_alt_f_ignored_outside_conversation(self, mock_notify, mock_sound,
                                                       mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        toggled = []
        mgr = _make_manager(on_conv_feedback=lambda: toggled.append(1))
        mgr._state = mgr._STATE_IDLE
        _ctrl_alt_press(mgr, 'f', mock_kb)
        assert toggled == []

    def test_ctrl_alt_p_triggers_reprocess(self, mock_notify, mock_sound,
                                             mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        reprocessed = []
        mgr = _make_manager(on_reprocess=lambda: reprocessed.append(1))
        _ctrl_alt_press(mgr, 'p', mock_kb)
        assert reprocessed == [1]

    # --- exception safety ---

    def test_conv_start_exception_resets_state_to_idle(self, mock_notify, mock_sound,
                                                         mock_cfg, mock_kb, mock_glib):
        """If _on_conv_start_cb raises, state resets to IDLE so recording still works."""
        self._setup_idle_add(mock_glib)

        def crashing_cb():
            raise AttributeError("simulated GTK crash")

        mgr = _make_manager(on_conv_start=crashing_cb)
        _ctrl_alt_press(mgr, 'c', mock_kb)
        assert mgr._state == mgr._STATE_IDLE

    def test_record_works_after_conv_start_exception(self, mock_notify, mock_sound,
                                                       mock_cfg, mock_kb, mock_glib):
        """Ctrl+Alt+R must work even after a crashing conversation start."""
        self._setup_idle_add(mock_glib)

        def crashing_cb():
            raise RuntimeError("window creation failed")

        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager(on_conv_start=crashing_cb)
            _ctrl_alt_press(mgr, 'c', mock_kb)  # crashes, state recovers to IDLE
            assert mgr._state == mgr._STATE_IDLE
            _ctrl_alt_press(mgr, 'r', mock_kb)  # must start recording normally
            assert mgr._state == mgr._STATE_RECORDING

    def test_on_recording_start_cb_called(self, mock_notify, mock_sound,
                                           mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        started = []
        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager(on_start=lambda: started.append(1))
            _ctrl_alt_press(mgr, 'r', mock_kb)
            assert started == [1]

    def test_on_recorder_error_resets_state(self, mock_notify, mock_sound,
                                             mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        errors = []
        mgr = _make_manager(on_error=lambda m: errors.append(m))
        mgr._state = mgr._STATE_RECORDING
        mgr._on_recorder_error("mic disconnected")
        assert mgr._state == mgr._STATE_IDLE
        assert errors == ["mic disconnected"]

    def test_key_letter_char_fallback(self, mock_notify, mock_sound,
                                       mock_cfg, mock_kb, mock_glib):
        """_key_letter falls back to key.char when vk is absent."""
        from linux_speech_flow.hotkey import HotkeyManager
        key = MagicMock(spec=['char'])
        key.char = 'r'
        assert HotkeyManager._key_letter(key) == 'r'

    def test_stop_recording_cancel_true(self, mock_notify, mock_sound,
                                         mock_cfg, mock_kb, mock_glib):
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
