"""Tests for transcript output functions (copy/paste/save) and ConversationManager silence logic."""
import time
from unittest.mock import MagicMock, patch, call
import pytest


# ── TranscriptOutputWindow action functions ──────────────────────────────────

class TestTranscriptCopy:
    def test_calls_copy_to_clipboard(self):
        with patch("linux_speech_flow.injector.copy_to_clipboard") as mock_copy:
            from linux_speech_flow.conversation_dialog import _do_transcript_copy
            result = _do_transcript_copy("hello world")
        mock_copy.assert_called_once_with("hello world")
        assert result == "Copied to clipboard."

    def test_empty_transcript(self):
        with patch("linux_speech_flow.injector.copy_to_clipboard") as mock_copy:
            from linux_speech_flow.conversation_dialog import _do_transcript_copy
            result = _do_transcript_copy("")
        mock_copy.assert_called_once_with("")
        assert result == "Copied to clipboard."


class TestTranscriptPaste:
    def test_calls_paste_text(self):
        wi = {"window_id": "0xabc", "wm_class": "code"}
        with patch("linux_speech_flow.injector.paste_text") as mock_paste:
            from linux_speech_flow.conversation_dialog import _do_transcript_paste
            result = _do_transcript_paste("hello", wi)
        mock_paste.assert_called_once_with("hello", wi)
        assert result == "Pasted to active window."

    def test_empty_window_info(self):
        with patch("linux_speech_flow.injector.paste_text") as mock_paste:
            from linux_speech_flow.conversation_dialog import _do_transcript_paste
            _do_transcript_paste("text", {})
        mock_paste.assert_called_once_with("text", {})


class TestTranscriptSave:
    def test_saves_file_with_transcript(self, tmp_path):
        metadata = {
            "date": "2025-01-01T10:00:00",
            "duration": "1m 00s",
            "chunk_count": 2,
            "models_used": "",
        }
        with patch("linux_speech_flow.conversation_dialog.load_config",
                   return_value={"conv_save_dir": str(tmp_path)}):
            from linux_speech_flow.conversation_dialog import _do_transcript_save
            result = _do_transcript_save("my transcript text", metadata)

        assert result.startswith("Saved:")
        saved = list(tmp_path.glob("*.txt"))
        assert len(saved) == 1
        content = saved[0].read_text()
        assert "my transcript text" in content

    def test_returns_saved_path(self, tmp_path):
        metadata = {
            "date": "2025-01-01T10:00:00",
            "duration": "0m 30s",
            "chunk_count": 1,
            "models_used": "",
        }
        with patch("linux_speech_flow.conversation_dialog.load_config",
                   return_value={"conv_save_dir": str(tmp_path)}):
            from linux_speech_flow.conversation_dialog import _do_transcript_save
            result = _do_transcript_save("content", metadata)

        assert str(tmp_path) in result

    def test_creates_save_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "new" / "subdir"
        metadata = {
            "date": "2025-01-01T10:00:00",
            "duration": "0m 10s",
            "chunk_count": 1,
            "models_used": "",
        }
        with patch("linux_speech_flow.conversation_dialog.load_config",
                   return_value={"conv_save_dir": str(new_dir)}):
            from linux_speech_flow.conversation_dialog import _do_transcript_save
            _do_transcript_save("text", metadata)

        assert new_dir.exists()


# ── ConversationManager silence / heartbeat logic ────────────────────────────

def _make_manager(mock_glib):
    """Build a ConversationManager with all GTK dependencies patched out."""
    mock_glib.timeout_add_seconds.return_value = 99
    mock_glib.timeout_add.return_value = 98
    mock_glib.source_remove.return_value = True
    mock_glib.idle_add.side_effect = lambda f, *a: f(*a)
    from linux_speech_flow.conversation_manager import ConversationManager
    mgr = ConversationManager(application=None, on_session_complete=None, on_tray_state=None)
    mgr._status_window = None
    mgr._silence_dialog = None
    return mgr


@patch("linux_speech_flow.conversation_manager.GLib")
class TestSpeechHeartbeat:
    def test_renews_warn_timer_when_speaking(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._state = "conversation"
        mgr._last_silence_frames = 0   # user is speaking
        mgr._warn_timer = 42
        mock_glib.timeout_add_seconds.return_value = 99

        result = mgr._on_speech_heartbeat()

        assert result is True
        mock_glib.source_remove.assert_called_with(42)
        assert mgr._warn_timer == 99

    def test_does_not_renew_when_silent(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._state = "conversation"
        mgr._last_silence_frames = 15  # user has been silent 15 frames
        mock_glib.source_remove.reset_mock()

        mgr._on_speech_heartbeat()

        mock_glib.source_remove.assert_not_called()

    def test_does_not_renew_before_first_tick(self, mock_glib):
        """_last_silence_frames = -1 means no audio data received yet."""
        mgr = _make_manager(mock_glib)
        mgr._state = "conversation"
        mgr._last_silence_frames = -1
        mock_glib.source_remove.reset_mock()

        mgr._on_speech_heartbeat()

        mock_glib.source_remove.assert_not_called()

    def test_returns_false_when_idle(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._state = "idle"

        result = mgr._on_speech_heartbeat()

        assert result is False

    def test_updates_status_window_baseline_when_speaking(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._state = "conversation"
        mgr._last_silence_frames = 0
        mgr._warn_timer = None
        sw = MagicMock()
        mgr._status_window = sw

        mgr._on_speech_heartbeat()

        sw.set_silence_baseline.assert_called_once()


@patch("linux_speech_flow.conversation_manager.GLib")
class TestSilenceTick:
    def test_voice_detected_resets_offset_and_timers(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._state = "conversation"
        mgr._warn_timer = 42
        mgr._stop_timer = None
        mgr._last_silence_frames = 10
        mgr._silence_offset_sec = 5
        mock_glib.timeout_add_seconds.return_value = 99

        result = mgr._on_silence_tick(0)

        assert result is False
        assert mgr._silence_offset_sec == 0
        assert mgr._last_silence_frames == 0
        mock_glib.source_remove.assert_called_with(42)
        assert mgr._warn_timer == 99

    def test_silence_frames_accumulate(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._state = "conversation"
        mgr._warn_timer = None
        mgr._stop_timer = None
        mgr._last_silence_frames = 0
        mgr._silence_offset_sec = 0

        mgr._on_silence_tick(5)

        assert mgr._last_silence_frames == 5
        assert mgr._silence_offset_sec == 0  # no boundary crossed

    def test_chunk_boundary_accumulates_offset(self, mock_glib):
        """When frames go backwards, prior silence carried forward."""
        mgr = _make_manager(mock_glib)
        mgr._state = "conversation"
        mgr._warn_timer = None
        mgr._stop_timer = None
        mgr._last_silence_frames = 20   # was at 20 (2s silence) before boundary
        mgr._silence_offset_sec = 0

        mgr._on_silence_tick(3)  # new chunk: only 3 frames in so far → went backwards

        assert mgr._silence_offset_sec == int(20 * 0.1)  # = 2s carried forward

    def test_silence_display_forwarded_to_status_window(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._state = "conversation"
        mgr._warn_timer = None
        mgr._stop_timer = None
        mgr._last_silence_frames = 0
        sw = MagicMock()
        mgr._status_window = sw

        mgr._on_silence_tick(10)

        sw.update_silence.assert_called_once_with(int(10 * 0.1))


@patch("linux_speech_flow.conversation_manager.GLib")
class TestInFlightTracking:
    def test_in_flight_incremented_on_chunk_ready(self, mock_glib):
        mock_glib.idle_add.return_value = True
        mock_glib.timeout_add_seconds.return_value = 99
        mgr = _make_manager(mock_glib)
        mgr._state = "conversation"
        mgr._session_start = time.monotonic()
        mgr._warn_timer = None
        mgr._stop_timer = None

        with patch("linux_speech_flow.conversation_manager.threading") as mock_th:
            mock_thread = MagicMock()
            mock_th.Thread.return_value = mock_thread
            mgr._on_chunk_ready("/tmp/chunk_0000.wav")

        assert mgr._in_flight == 1
        mock_thread.start.assert_called_once()

    def test_on_thread_done_decrements_in_flight(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._in_flight = 2
        mgr._session_ending = False

        mgr._on_thread_done()

        assert mgr._in_flight == 1

    def test_on_thread_done_triggers_finish_when_last_and_ending(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._in_flight = 1
        mgr._session_ending = True
        mgr._chunk_texts = ["hello"]
        mgr._chunk_count = 1
        mgr._session_start = time.monotonic()
        finish_called = []

        with patch.object(mgr, "_finish_session", side_effect=lambda: finish_called.append(1)):
            mgr._on_thread_done()

        assert len(finish_called) == 1
        assert mgr._session_ending is False

    def test_on_thread_done_does_not_finish_when_more_threads(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._in_flight = 2
        mgr._session_ending = True
        finish_called = []

        with patch.object(mgr, "_finish_session", side_effect=lambda: finish_called.append(1)):
            mgr._on_thread_done()

        assert len(finish_called) == 0

    def test_try_finish_calls_finish_when_zero_in_flight(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._in_flight = 0
        mgr._session_ending = True
        mgr._chunk_texts = []
        mgr._chunk_count = 0
        mgr._session_start = time.monotonic()
        finish_called = []

        with patch.object(mgr, "_finish_session", side_effect=lambda: finish_called.append(1)):
            mgr._try_finish_after_stop()

        assert len(finish_called) == 1

    def test_try_finish_defers_when_threads_still_running(self, mock_glib):
        mgr = _make_manager(mock_glib)
        mgr._in_flight = 3
        mgr._session_ending = True
        finish_called = []

        with patch.object(mgr, "_finish_session", side_effect=lambda: finish_called.append(1)):
            mgr._try_finish_after_stop()

        assert len(finish_called) == 0
        # session_ending stays True so _on_thread_done can fire _finish_session later
        assert mgr._session_ending is True

    def test_chunk_ready_allowed_during_session_ending(self, mock_glib):
        """Last chunk from recorder must be processed even after state = IDLE."""
        mock_glib.idle_add.return_value = True
        mock_glib.timeout_add_seconds.return_value = 99
        mgr = _make_manager(mock_glib)
        mgr._state = "idle"           # stop_session already set this
        mgr._session_ending = True    # but we're still draining
        mgr._session_start = time.monotonic()
        mgr._warn_timer = None
        mgr._stop_timer = None

        with patch("linux_speech_flow.conversation_manager.threading") as mock_th:
            mock_thread = MagicMock()
            mock_th.Thread.return_value = mock_thread
            mgr._on_chunk_ready("/tmp/last_chunk.wav")

        assert mgr._in_flight == 1  # chunk was processed, not dropped


# ── ConversationRecorder auto-calibration ────────────────────────────────────

@patch("linux_speech_flow.conversation_recorder.GLib")
class TestAutoCalibration:
    def _make_recorder(self):
        from linux_speech_flow.conversation_recorder import ConversationRecorder
        rec = ConversationRecorder(device_name=None)
        return rec

    def _make_pa_stub(self, rms_values):
        """PA stub that returns frames with given RMS levels."""
        import struct, math
        from linux_speech_flow.conversation_recorder import CHUNK_BYTES, SAMPLE_WIDTH
        frames = []
        n_samples = CHUNK_BYTES // SAMPLE_WIDTH
        for rms in rms_values:
            # Generate silence-like signal with target RMS
            amp = int(rms * 32768)
            # Alternate +amp/-amp to get exact RMS
            samples = [amp if i % 2 == 0 else -amp for i in range(n_samples)]
            raw = struct.pack(f"{n_samples}h", *samples)
            frames.append(raw)
        pa = MagicMock()
        pa.read.side_effect = frames + [b"\x00" * CHUNK_BYTES] * 1000
        return pa

    def test_calibration_sets_threshold(self, mock_glib):
        """Calibrated threshold = ambient_rms * CALIB_FACTOR, clamped."""
        import threading, struct
        from linux_speech_flow.conversation_recorder import (
            ConversationRecorder, MIN_GUARD_FRAMES, CALIB_FACTOR, CALIB_MIN, CALIB_MAX,
            CHUNK_BYTES, SAMPLE_WIDTH,
        )
        rec = ConversationRecorder(device_name=None)

        captured = []
        def fake_idle_add(fn, *args):
            captured.append((fn, args))
        mock_glib.idle_add.side_effect = fake_idle_add

        ambient_rms = 0.002
        n_samples = CHUNK_BYTES // SAMPLE_WIDTH
        amp = int(ambient_rms * 32768)
        ambient_frame = struct.pack(f"{n_samples}h", *[amp if i % 2 == 0 else -amp for i in range(n_samples)])
        silent_frame = b"\x00" * CHUNK_BYTES

        stop_event = threading.Event()
        rec._stop_event = stop_event

        # Set stop_event after MIN_GUARD_FRAMES + 1 reads so calibration completes
        call_count = [0]
        frames = [ambient_frame] * (MIN_GUARD_FRAMES + 1) + [silent_frame] * 200

        def read_side_effect(nbytes):
            idx = call_count[0]
            call_count[0] += 1
            if call_count[0] > MIN_GUARD_FRAMES + 1:
                stop_event.set()
            return frames[min(idx, len(frames) - 1)]

        pa = MagicMock()
        pa.read.side_effect = read_side_effect

        rec._on_chunk_ready = MagicMock()
        rec._on_error = MagicMock()
        rec._on_silence_tick = None
        rec._on_audio_level = None
        rec._on_threshold_calibrated = lambda v: captured.append(v)

        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            rec._record_one_chunk(pa, wav_path, 300, chunk_index=0)
        finally:
            try: os.unlink(wav_path)
            except: pass

        # Threshold should have been updated
        expected = max(CALIB_MIN, min(CALIB_MAX, ambient_rms * CALIB_FACTOR))
        assert abs(rec._silence_rms_threshold - expected) < 0.001

    def test_calibration_skipped_for_non_first_chunk(self, mock_glib):
        """chunk_index != 0 skips calibration to preserve threshold from chunk 0."""
        import threading
        from linux_speech_flow.conversation_recorder import ConversationRecorder, MIN_GUARD_FRAMES
        rec = ConversationRecorder(device_name=None)
        rec._silence_rms_threshold = 0.010  # set by chunk 0 calibration

        ambient_rms = 0.001  # very quiet — would lower threshold if calibrated
        rms_sequence = [ambient_rms] * (MIN_GUARD_FRAMES + 5) + [0.0] * 50
        pa = self._make_pa_stub(rms_sequence)

        stop_event = threading.Event()
        stop_event.set()
        rec._stop_event = stop_event
        rec._on_chunk_ready = MagicMock()
        rec._on_error = MagicMock()
        rec._on_silence_tick = None
        rec._on_audio_level = None
        rec._on_threshold_calibrated = MagicMock()

        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            rec._record_one_chunk(pa, wav_path, 30, chunk_index=1)  # not first chunk
        finally:
            try: os.unlink(wav_path)
            except: pass

        # Threshold unchanged
        assert abs(rec._silence_rms_threshold - 0.010) < 0.001
        rec._on_threshold_calibrated.assert_not_called()

    def test_calibration_skipped_when_speaking_during_guard(self, mock_glib):
        """If guard-period RMS >= current threshold, user was speaking — skip calibration."""
        import threading, struct
        from linux_speech_flow.conversation_recorder import (
            ConversationRecorder, MIN_GUARD_FRAMES, CHUNK_BYTES, SAMPLE_WIDTH,
        )
        rec = ConversationRecorder(device_name=None)
        default_threshold = rec._silence_rms_threshold  # 0.005

        # Guard frames contain speech-level signal (above threshold)
        speech_rms = 0.020  # clearly above 0.005
        n_samples = CHUNK_BYTES // SAMPLE_WIDTH
        amp = int(speech_rms * 32768)
        speech_frame = struct.pack(f"{n_samples}h", *[amp if i % 2 == 0 else -amp for i in range(n_samples)])

        stop_event = threading.Event()
        rec._stop_event = stop_event
        call_count = [0]
        frames = [speech_frame] * (MIN_GUARD_FRAMES + 2)

        def read_side_effect(nbytes):
            idx = call_count[0]
            call_count[0] += 1
            if call_count[0] > MIN_GUARD_FRAMES + 1:
                stop_event.set()
            return frames[min(idx, len(frames) - 1)]

        pa = MagicMock()
        pa.read.side_effect = read_side_effect
        rec._on_chunk_ready = MagicMock()
        rec._on_error = MagicMock()
        rec._on_silence_tick = None
        rec._on_audio_level = None
        rec._on_threshold_calibrated = MagicMock()

        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            rec._record_one_chunk(pa, wav_path, 300, chunk_index=0)
        finally:
            try: os.unlink(wav_path)
            except: pass

        # Threshold should be UNCHANGED because guard frames had speech-level signal
        assert abs(rec._silence_rms_threshold - default_threshold) < 0.001
        rec._on_threshold_calibrated.assert_not_called()
