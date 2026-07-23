"""Tests for TranscriptionPipeline._process() and submit().

The worker thread is suppressed so _process() can be called directly.
External dependencies (groq, GLib, paste_text, play_sound, send_notification,
shutil) are mocked throughout.
"""

from unittest.mock import MagicMock, patch

import groq as groq_module

from linux_speech_flow.transcription import MIN_TRANSCRIPT_LEN, TranscriptionPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline(**kwargs):
    """Create a TranscriptionPipeline with the worker thread suppressed."""
    with patch("linux_speech_flow.transcription.threading.Thread"):
        return TranscriptionPipeline(**kwargs)


def _window_info(**extra):
    info = {
        "window_id": "0x1234",
        "wm_class": "gedit",
        "category": "other",
        "session": "x11",
        "leaked_hotkey_count": 0,
    }
    info.update(extra)
    return info


def _config(**extra):
    cfg = {
        "groq_api_key": "test-key",
        "sounds_enabled": False,
        "sounds_output_device": "",
        "processing_sound_enabled": False,
        "success_sound_enabled": False,
        "processing_sound_file": "",
        "success_sound_file": "",
        "whisper_model": "whisper-large-v3-turbo",
        "llm_model": "llama-4-scout",
        "llm_system_prompt": "",
        "vocabulary": [],
        "history_max_entries": 20,
    }
    cfg.update(extra)
    return cfg


def _mock_groq_client(transcript="Hello world.", llm_result="Hello world."):
    """Build a mock groq.Groq() instance with fixed API responses."""
    client = MagicMock()
    client.audio.transcriptions.create.return_value = transcript
    response = MagicMock()
    response.choices[0].message.content = llm_result
    client.chat.completions.create.return_value = response
    return client


def _auth_exc():
    return groq_module.AuthenticationError.__new__(groq_module.AuthenticationError)


# ---------------------------------------------------------------------------
# _process() — happy path
# ---------------------------------------------------------------------------


@patch("linux_speech_flow.transcription.GLib")
@patch("linux_speech_flow.transcription.send_notification")
@patch("linux_speech_flow.transcription.play_sound")
@patch("linux_speech_flow.transcription.paste_text")
class TestProcessHappyPath:
    def test_pastes_llm_result(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()
        client = _mock_groq_client(transcript="hello world", llm_result="Hello world.")

        with patch("linux_speech_flow.llm_router.groq.Groq", return_value=client):
            pipeline._process(str(wav), _window_info(), _config())

        mock_paste.assert_called_once()
        assert "Hello world." in mock_paste.call_args[0][0]

    def test_deletes_wav_after_paste(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()

        with patch(
            "linux_speech_flow.llm_router.groq.Groq",
            return_value=_mock_groq_client(),
        ):
            pipeline._process(str(wav), _window_info(), _config())

        assert not wav.exists()

    def test_calls_on_paste_complete(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        done = []
        pipeline = _make_pipeline(on_paste_complete=lambda: done.append(1))
        mock_glib.idle_add.side_effect = lambda fn, *a: fn(*a)

        with patch(
            "linux_speech_flow.llm_router.groq.Groq",
            return_value=_mock_groq_client(),
        ):
            pipeline._process(str(wav), _window_info(), _config())

        assert done == [1]


# ---------------------------------------------------------------------------
# _process() — Whisper errors
# ---------------------------------------------------------------------------


@patch("linux_speech_flow.transcription.GLib")
@patch("linux_speech_flow.transcription.send_notification")
@patch("linux_speech_flow.transcription.play_sound")
@patch("linux_speech_flow.transcription.paste_text")
class TestProcessWhisperErrors:
    def test_auth_error_no_paste(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()

        with (
            patch("linux_speech_flow.llm_router.groq.Groq"),
            patch.object(pipeline, "_transcribe", side_effect=_auth_exc()),
            patch("linux_speech_flow.transcription.shutil.move"),
        ):
            pipeline._process(str(wav), _window_info(), _config())

        mock_paste.assert_not_called()

    def test_auth_error_moves_wav_to_failed(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()

        with (
            patch("linux_speech_flow.llm_router.groq.Groq"),
            patch.object(pipeline, "_transcribe", side_effect=_auth_exc()),
            patch("linux_speech_flow.transcription.shutil.move") as mock_move,
        ):
            pipeline._process(str(wav), _window_info(), _config())

        mock_move.assert_called_once()
        assert "failed" in str(mock_move.call_args[0][1])

    def test_generic_whisper_error_no_paste(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()

        with (
            patch("linux_speech_flow.llm_router.groq.Groq"),
            patch.object(
                pipeline, "_transcribe", side_effect=OSError("disk read failed")
            ),
            patch("linux_speech_flow.transcription.shutil.move"),
        ):
            pipeline._process(str(wav), _window_info(), _config())

        mock_paste.assert_not_called()


# ---------------------------------------------------------------------------
# _process() — short transcript
# ---------------------------------------------------------------------------


@patch("linux_speech_flow.transcription.GLib")
@patch("linux_speech_flow.transcription.send_notification")
@patch("linux_speech_flow.transcription.play_sound")
@patch("linux_speech_flow.transcription.paste_text")
class TestProcessShortTranscript:
    def test_skips_paste(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()
        short = "hi"
        assert len(short.strip()) < MIN_TRANSCRIPT_LEN

        with patch(
            "linux_speech_flow.llm_router.groq.Groq",
            return_value=_mock_groq_client(transcript=short),
        ):
            pipeline._process(str(wav), _window_info(), _config())

        mock_paste.assert_not_called()

    def test_sends_no_speech_notification(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()
        mock_glib.idle_add.side_effect = lambda fn, *a: fn(*a)

        with patch(
            "linux_speech_flow.llm_router.groq.Groq",
            return_value=_mock_groq_client(transcript="hi"),
        ):
            pipeline._process(str(wav), _window_info(), _config())

        titles = [c[0][0] for c in mock_notify.call_args_list]
        assert any("No speech" in t for t in titles)


# ---------------------------------------------------------------------------
# _process() — LLM failure fallback
# ---------------------------------------------------------------------------


@patch("linux_speech_flow.transcription.GLib")
@patch("linux_speech_flow.transcription.send_notification")
@patch("linux_speech_flow.transcription.play_sound")
@patch("linux_speech_flow.transcription.paste_text")
class TestProcessLlmFailure:
    def test_pastes_raw_transcript_on_llm_failure(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()
        client = _mock_groq_client(transcript="raw whisper output")
        client.chat.completions.create.side_effect = Exception("LLM timeout")

        with patch("linux_speech_flow.llm_router.groq.Groq", return_value=client):
            pipeline._process(str(wav), _window_info(), _config())

        mock_paste.assert_called_once()
        assert "raw whisper output" in mock_paste.call_args[0][0]

    def test_notifies_user_of_llm_failure(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()
        mock_glib.idle_add.side_effect = lambda fn, *a: fn(*a)
        client = _mock_groq_client(transcript="raw whisper output")
        client.chat.completions.create.side_effect = Exception("LLM timeout")

        with patch("linux_speech_flow.llm_router.groq.Groq", return_value=client):
            pipeline._process(str(wav), _window_info(), _config())

        all_args = [str(c) for c in mock_notify.call_args_list]
        assert any("LLM" in a for a in all_args)


# ---------------------------------------------------------------------------
# _process() — batch output path
# ---------------------------------------------------------------------------


@patch("linux_speech_flow.transcription.GLib")
@patch("linux_speech_flow.transcription.send_notification")
@patch("linux_speech_flow.transcription.play_sound")
@patch("linux_speech_flow.transcription.paste_text")
class TestProcessBatchPath:
    def test_no_paste_when_batch_path_set(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        output_file = tmp_path / "batch.txt"
        output_file.write_text("")
        pipeline = _make_pipeline()
        info = _window_info(batch_output_path=str(output_file))

        with (
            patch(
                "linux_speech_flow.llm_router.groq.Groq",
                return_value=_mock_groq_client(),
            ),
            patch("subprocess.Popen"),
        ):
            pipeline._process(str(wav), info, _config())

        mock_paste.assert_not_called()

    def test_appends_result_to_batch_file(
        self, mock_paste, mock_sound, mock_notify, mock_glib, tmp_path
    ):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        output_file = tmp_path / "batch.txt"
        output_file.write_text("")
        pipeline = _make_pipeline()
        info = _window_info(batch_output_path=str(output_file))
        client = _mock_groq_client(
            transcript="dictated text", llm_result="Dictated text."
        )

        with (
            patch("linux_speech_flow.llm_router.groq.Groq", return_value=client),
            patch("subprocess.Popen"),
        ):
            pipeline._process(str(wav), info, _config())

        assert "Dictated text." in output_file.read_text()


# ---------------------------------------------------------------------------
# submit() — leaked_hotkey_count invariant (the critical bug fix)
# ---------------------------------------------------------------------------


class TestSubmitLeakedHotkeyCount:
    def test_count_zero_when_stop_was_hotkey_true(self, tmp_path):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()

        with (
            patch(
                "linux_speech_flow.transcription.load_config",
                return_value={"app_categories": {}},
            ),
            patch(
                "linux_speech_flow.transcription.get_active_window_info",
                return_value={},
            ),
        ):
            pipeline.submit(str(wav), stop_was_hotkey=True)

        _, window_info, _ = pipeline._queue.get_nowait()
        assert window_info["leaked_hotkey_count"] == 0

    def test_count_zero_when_stop_was_hotkey_false(self, tmp_path):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF")
        pipeline = _make_pipeline()

        with (
            patch(
                "linux_speech_flow.transcription.load_config",
                return_value={"app_categories": {}},
            ),
            patch(
                "linux_speech_flow.transcription.get_active_window_info",
                return_value={},
            ),
        ):
            pipeline.submit(str(wav), stop_was_hotkey=False)

        _, window_info, _ = pipeline._queue.get_nowait()
        assert window_info["leaked_hotkey_count"] == 0
