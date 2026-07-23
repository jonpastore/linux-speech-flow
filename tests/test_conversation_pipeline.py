"""Tests for ConversationPipeline, coalesce_file, and conv_filename."""

import json
from unittest.mock import MagicMock, patch

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_pipeline():
    """ConversationPipeline with mocked Groq client (no API calls)."""
    with (
        patch(
            "linux_speech_flow.conversation_pipeline.load_config",
            return_value={"groq_api_key": "test-key"},
        ),
        patch("linux_speech_flow.conversation_pipeline.Groq"),
    ):
        from linux_speech_flow.conversation_pipeline import ConversationPipeline

        return ConversationPipeline()


_META = {
    "date": "2025-01-01T10:00:00",
    "duration": "2m 30s",
    "chunk_count": 5,
    "models_used": "groq",
}

_GOOD_RESULT = {
    "title": "Meeting",
    "summary": "We talked.",
    "confidence": 0.9,
    "questions": [],
    "action_items": [],
}


# ── conv_filename ─────────────────────────────────────────────────────────────


class TestConvFilename:
    def test_timestamp_format(self):
        from linux_speech_flow.conversation_pipeline import conv_filename

        name = conv_filename("test")
        assert name.endswith(".txt")
        ts = name.split("_")[0]
        assert len(ts) == 15  # YYYYMMDDTHHmmSS
        assert ts[8] == "T"

    def test_special_chars_stripped(self):
        from linux_speech_flow.conversation_pipeline import conv_filename

        name = conv_filename("hello! @#$world")
        assert "!" not in name
        assert "@" not in name
        assert "#" not in name
        assert "$" not in name

    def test_spaces_become_dashes(self):
        from linux_speech_flow.conversation_pipeline import conv_filename

        name = conv_filename("hello world")
        assert "hello-world" in name

    def test_title_truncated_at_50_chars(self):
        from linux_speech_flow.conversation_pipeline import conv_filename

        name = conv_filename("a" * 100)
        stem = name.replace(".txt", "")
        title_part = stem.split("_", 1)[1]
        assert len(title_part) <= 50

    def test_default_title_is_untitled(self):
        from linux_speech_flow.conversation_pipeline import conv_filename

        assert "untitled" in conv_filename()


# ── coalesce_file ─────────────────────────────────────────────────────────────


class TestCoalesceFile:
    def test_creates_file_with_required_sections(self, tmp_path):
        from linux_speech_flow.conversation_pipeline import coalesce_file

        path = str(tmp_path / "out.txt")
        coalesce_file(path, _META, "Great summary", [], "Transcript text")
        content = open(path).read()
        assert "## Summary" in content
        assert "Great summary" in content
        assert "## Transcript" in content
        assert "Transcript text" in content

    def test_metadata_written(self, tmp_path):
        from linux_speech_flow.conversation_pipeline import coalesce_file

        path = str(tmp_path / "out.txt")
        coalesce_file(path, _META, "s", [], "t")
        content = open(path).read()
        assert "Date: 2025-01-01T10:00:00" in content
        assert "Duration: 2m 30s" in content
        assert "Chunks: 5" in content
        assert "Models: groq" in content

    def test_qa_section_present_when_rounds_given(self, tmp_path):
        from linux_speech_flow.conversation_pipeline import coalesce_file

        path = str(tmp_path / "out.txt")
        qa = [{"question": "What happened?", "answer": "Not much."}]
        coalesce_file(path, _META, "sum", qa, "text")
        content = open(path).read()
        assert "## Q&A" in content
        assert "What happened?" in content
        assert "Not much." in content

    def test_qa_section_absent_when_no_rounds(self, tmp_path):
        from linux_speech_flow.conversation_pipeline import coalesce_file

        path = str(tmp_path / "out.txt")
        coalesce_file(path, _META, "sum", [], "text")
        assert "## Q&A" not in open(path).read()

    def test_multiple_qa_rounds_all_written(self, tmp_path):
        from linux_speech_flow.conversation_pipeline import coalesce_file

        path = str(tmp_path / "out.txt")
        qa = [
            {"question": "Q1", "answer": "A1"},
            {"question": "Q2", "answer": "A2"},
        ]
        coalesce_file(path, _META, "sum", qa, "text")
        content = open(path).read()
        assert "Q1" in content and "A1" in content
        assert "Q2" in content and "A2" in content

    def test_overwrites_existing_file(self, tmp_path):
        from linux_speech_flow.conversation_pipeline import coalesce_file

        path = str(tmp_path / "out.txt")
        open(path, "w").write("old content")
        coalesce_file(path, _META, "new", [], "new text")
        content = open(path).read()
        assert "old content" not in content
        assert "new text" in content


# ── _parse_result ─────────────────────────────────────────────────────────────


class TestParseResult:
    def test_valid_json_all_fields(self):
        p = _make_pipeline()
        raw = json.dumps(
            {
                "title": "My Meeting",
                "summary": "We discussed things.",
                "confidence": 0.9,
                "questions": ["What next?"],
                "action_items": ["Send email"],
            }
        )
        r = p._parse_result(raw)
        assert r["title"] == "My Meeting"
        assert r["summary"] == "We discussed things."
        assert r["confidence"] == 0.9
        assert r["questions"] == ["What next?"]
        assert r["action_items"] == ["Send email"]

    def test_missing_fields_get_defaults(self):
        p = _make_pipeline()
        r = p._parse_result(json.dumps({"title": "Only title"}))
        assert r["title"] == "Only title"
        assert r["summary"] == ""
        assert r["confidence"] == 0.0
        assert r["questions"] == []
        assert r["action_items"] == []

    def test_invalid_json_returns_raw_as_summary(self):
        p = _make_pipeline()
        r = p._parse_result("not json at all")
        assert r["title"] == "untitled"
        assert r["summary"] == "not json at all"
        assert r["confidence"] == 0.0

    def test_none_input_returns_defaults(self):
        p = _make_pipeline()
        r = p._parse_result(None)
        assert r["title"] == "untitled"
        assert r["confidence"] == 0.0

    def test_confidence_coerced_to_float(self):
        p = _make_pipeline()
        r = p._parse_result(json.dumps({"confidence": "0.85"}))
        assert isinstance(r["confidence"], float)
        assert r["confidence"] == pytest.approx(0.85)

    def test_title_coerced_to_str(self):
        p = _make_pipeline()
        r = p._parse_result(json.dumps({"title": 42}))
        assert r["title"] == "42"


# ── synthesize ────────────────────────────────────────────────────────────────


class TestSynthesize:
    def test_calls_groq_meta_model(self):
        p = _make_pipeline()
        p._call_groq = MagicMock(return_value=_GOOD_RESULT)
        model_results = {
            "grok": {**_GOOD_RESULT, "title": "A"},
            "gemini": {**_GOOD_RESULT, "title": "B"},
        }
        result = p.synthesize(model_results, "groq", config={})
        assert result == _GOOD_RESULT
        p._call_groq.assert_called_once()

    def test_calls_grok_meta_model(self):
        p = _make_pipeline()
        p._call_grok = MagicMock(return_value=_GOOD_RESULT)
        result = p.synthesize({"groq": _GOOD_RESULT}, "grok", config={})
        assert result == _GOOD_RESULT
        p._call_grok.assert_called_once()

    def test_fallback_on_meta_failure(self):
        p = _make_pipeline()
        p._call_groq = MagicMock(side_effect=Exception("API error"))
        good = {**_GOOD_RESULT, "title": "Fallback"}
        model_results = {"error_model": {"error": "failed"}, "good": good}
        result = p.synthesize(model_results, "groq", config={})
        assert result == good

    def test_all_errors_returns_empty_dict(self):
        p = _make_pipeline()
        p._call_groq = MagicMock(side_effect=Exception("fail"))
        result = p.synthesize({"groq": {"error": "failed"}}, "groq", config={})
        assert result["title"] == "untitled"
        assert result["confidence"] == 0.0
        assert result["questions"] == []

    def test_loads_config_when_none_passed(self):
        p = _make_pipeline()
        p._call_groq = MagicMock(return_value=_GOOD_RESULT)
        with patch(
            "linux_speech_flow.conversation_pipeline.load_config", return_value={}
        ):
            result = p.synthesize({"groq": _GOOD_RESULT}, "groq", config=None)
        assert result == _GOOD_RESULT


# ── analyze ───────────────────────────────────────────────────────────────────


class TestAnalyze:
    def test_single_model_returns_direct_result(self):
        p = _make_pipeline()
        p._call_groq = MagicMock(return_value=_GOOD_RESULT)
        with patch(
            "linux_speech_flow.conversation_pipeline.load_config", return_value={}
        ):
            result = p.analyze("transcript", "prompt", "context", ["groq"])
        assert result == _GOOD_RESULT

    def test_multiple_models_calls_synthesize(self):
        p = _make_pipeline()
        p._call_groq = MagicMock(return_value={**_GOOD_RESULT, "title": "G"})
        p._call_grok = MagicMock(return_value={**_GOOD_RESULT, "title": "GK"})
        synth = {**_GOOD_RESULT, "title": "Synthesized"}
        p.synthesize = MagicMock(return_value=synth)
        with patch(
            "linux_speech_flow.conversation_pipeline.load_config",
            return_value={"conv_meta_model": "groq"},
        ):
            result = p.analyze("t", "p", "ctx", ["groq", "grok"])
        p.synthesize.assert_called_once()
        assert result == synth

    def test_failed_model_returns_error_dict_for_single(self):
        p = _make_pipeline()
        p._call_groq = MagicMock(side_effect=Exception("network error"))
        with patch(
            "linux_speech_flow.conversation_pipeline.load_config", return_value={}
        ):
            result = p.analyze("t", "p", "ctx", ["groq"])
        assert "error" in result

    def test_groq_model_included_in_futures(self):
        p = _make_pipeline()
        p._call_groq = MagicMock(return_value=_GOOD_RESULT)
        with patch(
            "linux_speech_flow.conversation_pipeline.load_config", return_value={}
        ):
            p.analyze("t", "p", "ctx", ["groq"])
        p._call_groq.assert_called_once()

    def test_qualifying_answers_embedded_in_system_prompt(self):
        p = _make_pipeline()
        captured = {}

        def capture_call(system, content, config):
            captured["system"] = system
            return _GOOD_RESULT

        p._call_groq = capture_call
        with patch(
            "linux_speech_flow.conversation_pipeline.load_config", return_value={}
        ):
            p.analyze("t", "prompt", "my context here", ["groq"])
        assert "my context here" in captured["system"]


# ── transcribe_chunk_verbose ──────────────────────────────────────────────────


class TestTranscribeChunkVerbose:
    def _make_segment(self, avg_logprob):
        seg = MagicMock()
        seg.avg_logprob = avg_logprob
        return seg

    def test_returns_text_and_confidence(self, tmp_path):
        p = _make_pipeline()
        wav = tmp_path / "chunk.wav"
        wav.write_bytes(b"fake")
        seg = self._make_segment(-0.1)
        mock_resp = MagicMock()
        mock_resp.text = "Hello world"
        mock_resp.segments = [seg]
        p._groq.audio.transcriptions.create.return_value = mock_resp
        with patch(
            "linux_speech_flow.conversation_pipeline.load_config",
            return_value={"whisper_model": "whisper-large-v3-turbo"},
        ):
            text, confidence = p.transcribe_chunk_verbose(str(wav))
        assert text == "Hello world"
        import math

        assert confidence == pytest.approx(math.exp(-0.1), abs=1e-6)

    def test_empty_segments_returns_zero_confidence(self, tmp_path):
        p = _make_pipeline()
        wav = tmp_path / "chunk.wav"
        wav.write_bytes(b"fake")
        mock_resp = MagicMock()
        mock_resp.text = "Some text"
        mock_resp.segments = []
        p._groq.audio.transcriptions.create.return_value = mock_resp
        with patch(
            "linux_speech_flow.conversation_pipeline.load_config",
            return_value={},
        ):
            text, confidence = p.transcribe_chunk_verbose(str(wav))
        assert text == "Some text"
        assert confidence == 0.0

    def test_no_segments_attr_returns_zero_confidence(self, tmp_path):
        p = _make_pipeline()
        wav = tmp_path / "chunk.wav"
        wav.write_bytes(b"fake")
        mock_resp = MagicMock(spec=["text"])
        mock_resp.text = "Text"
        p._groq.audio.transcriptions.create.return_value = mock_resp
        with patch(
            "linux_speech_flow.conversation_pipeline.load_config",
            return_value={},
        ):
            text, confidence = p.transcribe_chunk_verbose(str(wav))
        assert text == "Text"
        assert confidence == 0.0

    def test_confidence_clamped_to_one(self, tmp_path):
        p = _make_pipeline()
        wav = tmp_path / "chunk.wav"
        wav.write_bytes(b"fake")
        seg = self._make_segment(0.5)  # positive logprob → exp > 1
        mock_resp = MagicMock()
        mock_resp.text = "x"
        mock_resp.segments = [seg]
        p._groq.audio.transcriptions.create.return_value = mock_resp
        with patch(
            "linux_speech_flow.conversation_pipeline.load_config",
            return_value={},
        ):
            _, confidence = p.transcribe_chunk_verbose(str(wav))
        assert confidence == pytest.approx(1.0)

    def test_transcribe_chunk_delegates_to_verbose(self, tmp_path):
        p = _make_pipeline()
        p.transcribe_chunk_verbose = MagicMock(return_value=("hello", 0.9))
        wav = tmp_path / "chunk.wav"
        wav.write_bytes(b"fake")
        result = p.transcribe_chunk(str(wav))
        assert result == "hello"
        p.transcribe_chunk_verbose.assert_called_once_with(str(wav))

    def test_api_error_propagates(self, tmp_path):
        p = _make_pipeline()
        wav = tmp_path / "chunk.wav"
        wav.write_bytes(b"fake")
        p._groq.audio.transcriptions.create.side_effect = Exception("API down")
        with (
            patch(
                "linux_speech_flow.conversation_pipeline.load_config",
                return_value={},
            ),
            pytest.raises(Exception, match="API down"),
        ):
            p.transcribe_chunk_verbose(str(wav))


# ── continue_qa ───────────────────────────────────────────────────────────────


class TestContinueQA:
    def test_delegates_to_analyze(self):
        p = _make_pipeline()
        updated = {**_GOOD_RESULT, "summary": "updated"}
        p.analyze = MagicMock(return_value=updated)
        result = p.continue_qa(
            current_result={"title": "old"},
            question="What did you mean?",
            answer="I meant X.",
            transcript="full transcript",
            models=["groq"],
        )
        assert result == updated
        p.analyze.assert_called_once()

    def test_transcript_and_models_passed_through(self):
        p = _make_pipeline()
        p.analyze = MagicMock(return_value=_GOOD_RESULT)
        p.continue_qa({}, "Q?", "A.", "my transcript", ["groq", "grok"])
        args = p.analyze.call_args[0]
        assert args[0] == "my transcript"
        assert args[3] == ["groq", "grok"]

    def test_qa_context_included_in_prompt(self):
        p = _make_pipeline()
        captured = {}

        def capture(transcript, prompt, qualifying_answers, models):
            captured["qualifying_answers"] = qualifying_answers
            return _GOOD_RESULT

        p.analyze = capture
        p.continue_qa({}, "What?", "This.", "t", ["groq"])
        assert "What?" in captured["qualifying_answers"]
        assert "This." in captured["qualifying_answers"]
