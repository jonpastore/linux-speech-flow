"""Tests for HotkeyManager state machine.

GLib.idle_add is patched to call callbacks synchronously so state transitions
are observable without a running GTK main loop. pynput.keyboard.Listener is
patched to avoid starting a real X11 keyboard grab.
"""
import sys
from unittest.mock import MagicMock, patch, call


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
    """Simulate a key press going through the pynput callback."""
    mgr._on_press(key)


# ---------------------------------------------------------------------------
# Module-level patches applied for the entire module
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

    def setup_method(self):
        # Reset module so patches apply cleanly
        pass

    def _setup_idle_add(self, mock_glib):
        """Make idle_add execute the function immediately and return False."""
        def immediate_idle_add(fn, *args):
            fn(*args)
            return False
        mock_glib.idle_add.side_effect = immediate_idle_add

    # --- basic guards ---

    def test_f9_ignored_before_mark_started(self, mock_notify, mock_sound,
                                             mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mgr = _make_manager()
        mgr._started = False
        _press(mgr, mock_kb.Key.f9)
        mock_glib.idle_add.assert_not_called()

    def test_f9_in_idle_transitions_to_recording(self, mock_notify, mock_sound,
                                                  mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager()
            assert mgr._state == mgr._STATE_IDLE
            _press(mgr, "f9")
            assert mgr._state == mgr._STATE_RECORDING

    def test_f9_in_recording_stops_recorder(self, mock_notify, mock_sound,
                                             mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager()
            _press(mgr, "f9")  # start
            assert mgr._state == mgr._STATE_RECORDING
            _press(mgr, "f9")  # stop
            mock_recorder.stop.assert_called_once_with(cancel=False)
            assert mgr._stop_was_f9 is True

    def test_esc_stops_recording_normally(self, mock_notify, mock_sound,
                                         mock_cfg, mock_kb, mock_glib):
        """ESC is a normal stop (cancel=False): audio is kept and transcribed.
        State remains RECORDING until the recorder thread fires _on_recorder_complete."""
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager()
            _press(mgr, "f9")
            _press(mgr, "esc")
            mock_recorder.stop.assert_called_once_with(cancel=False)
            assert mgr._stop_was_f9 is False  # ESC did not set the f9 stop flag

    def test_f9_ignored_in_recording_when_already_stopping(self, mock_notify,
                                                             mock_sound, mock_cfg,
                                                             mock_kb, mock_glib):
        """F9 during CONVERSATION state is ignored."""
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        mgr = _make_manager()
        mgr._state = mgr._STATE_CONVERSATION
        _press(mgr, "f9")
        mock_glib.idle_add.assert_not_called()

    # --- recorder complete callback ---

    def test_on_recorder_complete_resets_state_and_calls_cb(self, mock_notify,
                                                              mock_sound, mock_cfg,
                                                              mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        received = []
        mgr = _make_manager(on_complete=lambda p, f: received.append((p, f)))
        mgr._state = mgr._STATE_RECORDING
        mgr._stop_was_f9 = True
        mgr._on_recorder_complete("/tmp/test.wav")
        assert mgr._state == mgr._STATE_IDLE
        assert received == [("/tmp/test.wav", True)]

    def test_on_recorder_complete_stop_was_f9_false(self, mock_notify, mock_sound,
                                                     mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        received = []
        mgr = _make_manager(on_complete=lambda p, f: received.append((p, f)))
        mgr._state = mgr._STATE_RECORDING
        mgr._stop_was_f9 = False
        mgr._on_recorder_complete("/tmp/test.wav")
        assert received == [("/tmp/test.wav", False)]

    # --- conversation mode state transitions ---

    def test_f11_idle_transitions_to_conversation(self, mock_notify, mock_sound,
                                                   mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        started = []
        mgr = _make_manager(on_conv_start=lambda: started.append(1))
        _press(mgr, "f11")
        assert mgr._state == mgr._STATE_CONVERSATION
        assert started == [1]

    def test_f11_conversation_transitions_to_idle(self, mock_notify, mock_sound,
                                                   mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        stopped = []
        mgr = _make_manager(on_conv_stop=lambda: stopped.append(1))
        mgr._state = mgr._STATE_CONVERSATION
        _press(mgr, "f11")
        assert mgr._state == mgr._STATE_IDLE
        assert stopped == [1]

    def test_f11_ignored_in_recording_state(self, mock_notify, mock_sound,
                                             mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        mgr = _make_manager()
        mgr._state = mgr._STATE_RECORDING
        _press(mgr, "f11")
        assert mgr._state == mgr._STATE_RECORDING  # unchanged

    def test_f12_triggers_feedback_toggle_in_conversation(self, mock_notify, mock_sound,
                                                           mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        toggled = []
        mgr = _make_manager(on_conv_feedback=lambda: toggled.append(1))
        mgr._state = mgr._STATE_CONVERSATION
        _press(mgr, "f12")
        assert toggled == [1]

    def test_f12_ignored_outside_conversation(self, mock_notify, mock_sound,
                                               mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        toggled = []
        mgr = _make_manager(on_conv_feedback=lambda: toggled.append(1))
        mgr._state = mgr._STATE_IDLE
        _press(mgr, "f12")
        assert toggled == []

    # --- exception safety (F9 survives conv_start crash) ---

    def test_conv_start_exception_resets_state_to_idle(self, mock_notify, mock_sound,
                                                        mock_cfg, mock_kb, mock_glib):
        """If _on_conv_start_cb raises, state must reset to IDLE so F9 still works."""
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        def crashing_cb():
            raise AttributeError("simulated GTK crash")

        mgr = _make_manager(on_conv_start=crashing_cb)
        _press(mgr, "f11")
        # state must be IDLE, not CONVERSATION, so F9 can still record
        assert mgr._state == mgr._STATE_IDLE

    def test_f9_works_after_conv_start_exception(self, mock_notify, mock_sound,
                                                  mock_cfg, mock_kb, mock_glib):
        """F9 must be usable even after a crashing conversation start."""
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        def crashing_cb():
            raise RuntimeError("window creation failed")

        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager(on_conv_start=crashing_cb)
            _press(mgr, "f11")  # crashes but state recovers to IDLE
            assert mgr._state == mgr._STATE_IDLE
            _press(mgr, "f9")   # must start recording normally
            assert mgr._state == mgr._STATE_RECORDING

    def test_on_recording_start_cb_called(self, mock_notify, mock_sound,
                                          mock_cfg, mock_kb, mock_glib):
        self._setup_idle_add(mock_glib)
        mock_kb.Key.f9 = "f9"
        mock_kb.Key.f11 = "f11"
        mock_kb.Key.esc = "esc"
        mock_kb.Key.f10 = "f10"
        mock_kb.Key.f12 = "f12"

        started = []
        mock_recorder = MagicMock()
        with patch("linux_speech_flow.hotkey.AudioRecorder", return_value=mock_recorder):
            mgr = _make_manager(on_start=lambda: started.append(1))
            _press(mgr, "f9")
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
