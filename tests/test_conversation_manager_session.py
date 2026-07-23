"""Tests for ConversationManager start/stop/finish session flows.

Complements test_conversation_output.py (which covers silence/heartbeat logic).
"""

from unittest.mock import MagicMock, patch

# ── helpers ───────────────────────────────────────────────────────────────────

_CFG = {
    "sounds_enabled": False,
    "sounds_output_device": "",
    "conv_feedback_mode": "tray_only",
    "microphone": "",
    "conv_chunk_silence_sec": 3,
    "conv_silence_rms_threshold": 0.005,
    "conv_silence_warn_sec": 30,
    "conv_silence_stop_sec": 60,
    "conv_hard_limit_sec": 14400,
}


def _make_manager(mock_glib, cfg=None):
    mock_glib.timeout_add_seconds.return_value = 99
    mock_glib.timeout_add.return_value = 98
    mock_glib.source_remove.return_value = True
    mock_glib.idle_add.side_effect = lambda f, *a: f(*a)
    from linux_speech_flow.conversation_manager import ConversationManager

    mgr = ConversationManager(
        application=None,
        on_session_complete=MagicMock(),
        on_tray_state=MagicMock(),
    )
    mgr._status_window = None
    mgr._silence_dialog = None
    return mgr


# ── start_session ─────────────────────────────────────────────────────────────


@patch("linux_speech_flow.conversation_manager.GLib")
@patch("linux_speech_flow.conversation_manager.ConversationRecorder")
@patch("linux_speech_flow.conversation_manager.play_sound")
@patch("linux_speech_flow.conversation_manager.load_config", return_value=_CFG)
class TestStartSession:
    def test_transitions_state_to_conversation(
        self, mock_cfg, mock_sound, MockRecorder, mock_glib
    ):
        mgr = _make_manager(mock_glib)
        mgr.start_session()
        from linux_speech_flow.conversation_manager import _STATE_CONVERSATION

        assert mgr._state == _STATE_CONVERSATION

    def test_ignores_duplicate_start(
        self, mock_cfg, mock_sound, MockRecorder, mock_glib
    ):
        mgr = _make_manager(mock_glib)
        mgr.start_session()
        mgr.start_session()  # second call ignored
        assert MockRecorder.call_count == 1

    def test_resets_chunk_state(self, mock_cfg, mock_sound, MockRecorder, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._chunk_texts = ["leftover"]
        mgr._chunk_count = 3
        mgr.start_session()
        assert mgr._chunk_texts == []
        assert mgr._chunk_count == 0

    def test_creates_recorder_and_starts(
        self, mock_cfg, mock_sound, MockRecorder, mock_glib
    ):
        mgr = _make_manager(mock_glib)
        mgr.start_session()
        MockRecorder.assert_called_once()
        MockRecorder.return_value.start.assert_called_once()

    def test_notifies_tray_state(self, mock_cfg, mock_sound, MockRecorder, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr.start_session()
        mgr._on_tray_state.assert_called_with("conv_recording")

    def test_sets_hard_limit_timer(self, mock_cfg, mock_sound, MockRecorder, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr.start_session()
        assert mgr._hard_limit_timer is not None

    def test_plays_start_sound(self, mock_cfg, mock_sound, MockRecorder, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr.start_session()
        mock_sound.assert_called_once_with("start.wav", output_device="", enabled=False)


# ── stop_session ──────────────────────────────────────────────────────────────


@patch("linux_speech_flow.conversation_manager.GLib")
@patch("linux_speech_flow.conversation_manager.ConversationRecorder")
@patch("linux_speech_flow.conversation_manager.play_sound")
@patch("linux_speech_flow.conversation_manager.load_config", return_value=_CFG)
class TestStopSession:
    def test_ignored_when_not_in_conversation(
        self, mock_cfg, mock_sound, MockRecorder, mock_glib
    ):
        mgr = _make_manager(mock_glib)
        mgr.stop_session()  # state is idle — should be a no-op
        mock_sound.assert_not_called()

    def test_transitions_state_to_idle(
        self, mock_cfg, mock_sound, MockRecorder, mock_glib
    ):
        mgr = _make_manager(mock_glib)
        mgr.start_session()
        mgr.stop_session()
        from linux_speech_flow.conversation_manager import _STATE_IDLE

        assert mgr._state == _STATE_IDLE

    def test_calls_recorder_stop(self, mock_cfg, mock_sound, MockRecorder, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr.start_session()
        mgr.stop_session()
        MockRecorder.return_value.stop.assert_called_once()

    def test_sets_session_ending_flag(
        self, mock_cfg, mock_sound, MockRecorder, mock_glib
    ):
        mgr = _make_manager(mock_glib)
        mgr.start_session()
        # Prevent _finish_session from firing immediately via timeout_add
        mock_glib.timeout_add.return_value = 98
        mock_glib.timeout_add.side_effect = None  # don't auto-call
        mgr.stop_session()
        assert mgr._session_ending

    def test_cancels_all_timers(self, mock_cfg, mock_sound, MockRecorder, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr.start_session()
        mgr._warn_timer = 11
        mgr._stop_timer = 12
        mgr.stop_session()
        assert mock_glib.source_remove.called


# ── _finish_session ───────────────────────────────────────────────────────────


@patch("linux_speech_flow.conversation_manager.GLib")
@patch("linux_speech_flow.conversation_manager.play_sound")
@patch("linux_speech_flow.conversation_manager.load_config", return_value=_CFG)
class TestFinishSession:
    def _primed_manager(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._chunk_texts = ["Hello", "world"]
        mgr._chunk_count = 2
        mgr._session_start = 0.0
        mgr._recorder = MagicMock()
        return mgr

    def test_fires_on_session_complete(self, mock_cfg, mock_sound, mock_glib):
        mgr = self._primed_manager(mock_glib)
        mgr._finish_session()
        mgr._on_session_complete.assert_called_once()

    def test_transcript_is_joined_chunks(self, mock_cfg, mock_sound, mock_glib):
        mgr = self._primed_manager(mock_glib)
        mgr._finish_session()
        transcript = mgr._on_session_complete.call_args[0][0]
        assert transcript == "Hello world"

    def test_metadata_has_required_keys(self, mock_cfg, mock_sound, mock_glib):
        mgr = self._primed_manager(mock_glib)
        mgr._finish_session()
        metadata = mgr._on_session_complete.call_args[0][1]
        assert "date" in metadata
        assert "duration" in metadata
        assert "chunk_count" in metadata
        assert metadata["chunk_count"] == 2

    def test_tray_reset_to_idle(self, mock_cfg, mock_sound, mock_glib):
        mgr = self._primed_manager(mock_glib)
        mgr._finish_session()
        mgr._on_tray_state.assert_called_with("idle")

    def test_recorder_cleanup_called(self, mock_cfg, mock_sound, mock_glib):
        mgr = self._primed_manager(mock_glib)
        recorder = mgr._recorder
        mgr._finish_session()
        recorder.cleanup.assert_called_once()
        assert mgr._recorder is None

    def test_skips_on_session_complete_if_none(self, mock_cfg, mock_sound, mock_glib):
        mgr = self._primed_manager(mock_glib)
        mgr._on_session_complete = None
        mgr._finish_session()  # should not raise

    def test_empty_chunks_produces_empty_transcript(
        self, mock_cfg, mock_sound, mock_glib
    ):
        mgr = self._primed_manager(mock_glib)
        mgr._chunk_texts = []
        mgr._finish_session()
        transcript = mgr._on_session_complete.call_args[0][0]
        assert transcript == ""


# ── _on_recorder_done ────────────────────────────────────────────────────────


@patch("linux_speech_flow.conversation_manager.GLib")
@patch("linux_speech_flow.conversation_manager.play_sound")
@patch("linux_speech_flow.conversation_manager.load_config", return_value=_CFG)
class TestTryFinishAfterStop:
    def test_calls_finish_when_no_in_flight(self, mock_cfg, mock_sound, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._recorder = MagicMock()
        mgr._finish_session = MagicMock()
        mgr._in_flight = 0
        mgr._session_ending = True
        mgr._on_recorder_done()
        mgr._finish_session.assert_called_once()

    def test_defers_when_in_flight(self, mock_cfg, mock_sound, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._finish_session = MagicMock()
        mgr._in_flight = 2
        mgr._session_ending = True
        mgr._on_recorder_done()
        mgr._finish_session.assert_not_called()
        assert mgr._session_ending  # still waiting
