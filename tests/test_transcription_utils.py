"""Tests for pure-Python utility functions in transcription.py.

These tests cover text processing logic that requires no API calls,
no GTK, and no PulseAudio. The TranscriptionPipeline class itself
is not instantiated here — only the module-level helpers are tested.
"""
import pytest
from unittest.mock import MagicMock, patch

import groq

from linux_speech_flow.transcription import (
    _strip_hallucinations,
    _build_user_message,
    _classify_groq_error,
    _call_with_retry,
)


# ---------------------------------------------------------------------------
# _strip_hallucinations
# ---------------------------------------------------------------------------

class TestStripHallucinations:

    def test_clean_transcript_unchanged(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert _strip_hallucinations(text) == text

    def test_removes_trailing_thank_you(self):
        text = "Some real speech.\nthank you"
        result = _strip_hallucinations(text)
        assert "thank you" not in result
        assert "Some real speech." in result

    def test_removes_trailing_thank_you_period(self):
        text = "Hello world.\nthank you."
        result = _strip_hallucinations(text)
        assert result == "Hello world."

    def test_removes_thanks_for_watching(self):
        text = "Real content.\nthanks for watching"
        result = _strip_hallucinations(text)
        assert "thanks for watching" not in result

    def test_removes_subscribe(self):
        text = "Content here.\nsubscribe"
        result = _strip_hallucinations(text)
        assert "subscribe" not in result

    def test_removes_multiple_trailing_hallucinations(self):
        text = "Content.\nthank you\nsubscribe"
        result = _strip_hallucinations(text)
        assert result == "Content."

    def test_hallucination_mid_text_not_stripped(self):
        # Only trailing lines are stripped
        text = "thank you for helping me write this."
        result = _strip_hallucinations(text)
        assert result == text

    def test_case_insensitive_matching(self):
        text = "Content.\nThank You"
        result = _strip_hallucinations(text)
        assert "Thank You" not in result
        assert "Content." in result

    def test_empty_string_returns_empty(self):
        assert _strip_hallucinations("") == ""

    def test_only_hallucination_returns_empty(self):
        result = _strip_hallucinations("thank you")
        assert result == ""

    def test_strips_trailing_whitespace_from_result(self):
        result = _strip_hallucinations("Hello.\nthank you")
        assert result == "Hello."

    def test_like_and_subscribe_stripped(self):
        text = "Content.\nlike and subscribe."
        result = _strip_hallucinations(text)
        assert "like and subscribe" not in result


# ---------------------------------------------------------------------------
# _build_user_message
# ---------------------------------------------------------------------------

class TestBuildUserMessage:

    def test_includes_raw_transcript(self):
        result = _build_user_message("my transcript", {}, [])
        assert "my transcript" in result

    def test_includes_app_name_when_present(self):
        window_info = {"wm_class": "gedit", "title": "untitled.txt", "category": "editor"}
        result = _build_user_message("text", window_info, [])
        assert "gedit" in result

    def test_includes_window_title_when_present(self):
        window_info = {"wm_class": "gedit", "title": "report.docx", "category": "editor"}
        result = _build_user_message("text", window_info, [])
        assert "report.docx" in result

    def test_no_context_block_when_window_info_empty(self):
        result = _build_user_message("transcript text", {}, [])
        assert "<context>" not in result

    def test_includes_vocabulary_when_provided(self):
        vocab = ["kubernetes", "OAuth", "microservice"]
        result = _build_user_message("text", {}, vocab)
        assert "kubernetes" in result
        assert "OAuth" in result
        assert "microservice" in result

    def test_no_vocabulary_block_when_empty(self):
        result = _build_user_message("text", {}, [])
        assert "<vocabulary>" not in result

    def test_context_and_vocabulary_both_included(self):
        window_info = {"wm_class": "Terminal", "title": "bash", "category": "terminal"}
        vocab = ["kubectl", "helm"]
        result = _build_user_message("deploy the app", window_info, vocab)
        assert "<context>" in result
        assert "<vocabulary>" in result
        assert "kubectl" in result
        assert "Terminal" in result

    def test_category_included_in_context(self):
        window_info = {"wm_class": "gnome-terminal", "title": "~", "category": "terminal"}
        result = _build_user_message("text", window_info, [])
        assert "terminal" in result


# ---------------------------------------------------------------------------
# _classify_groq_error
# ---------------------------------------------------------------------------

class TestClassifyGroqError:

    def _make_exc(self, exc_class, status_code=None):
        """Create a minimal groq API error instance."""
        try:
            exc = exc_class.__new__(exc_class)
            exc.status_code = status_code
            exc.message = "test"
            return exc
        except Exception:
            return MagicMock(spec=exc_class)

    def test_auth_error_message(self):
        exc = groq.AuthenticationError.__new__(groq.AuthenticationError)
        result = _classify_groq_error(exc)
        assert "API key" in result or "Invalid" in result

    def test_rate_limit_message(self):
        exc = groq.RateLimitError.__new__(groq.RateLimitError)
        result = _classify_groq_error(exc)
        assert "limit" in result.lower() or "rate" in result.lower()

    def test_connection_error_message(self):
        exc = groq.APIConnectionError.__new__(groq.APIConnectionError)
        result = _classify_groq_error(exc)
        assert "network" in result.lower() or "connection" in result.lower()

    def test_unknown_api_error_includes_status_code(self):
        exc = groq.APIStatusError.__new__(groq.APIStatusError)
        exc.status_code = 500
        exc.message = "internal"
        exc.response = None
        exc.body = None
        result = _classify_groq_error(exc)
        assert "500" in result or "Groq" in result


# ---------------------------------------------------------------------------
# _call_with_retry
# ---------------------------------------------------------------------------

class TestCallWithRetry:

    def test_returns_result_on_first_success(self):
        fn = lambda: 42
        result = _call_with_retry(fn, retryable=(ValueError,))
        assert result == 42

    def test_raises_after_all_delays_exhausted(self):
        call_count = [0]

        def always_fails():
            call_count[0] += 1
            raise ConnectionError("network down")

        with pytest.raises(ConnectionError):
            _call_with_retry(always_fails, retryable=(ConnectionError,))

        # Called once per delay in FIBONACCI_DELAYS (5 delays)
        assert call_count[0] == 5

    def test_non_retryable_exception_raised_immediately(self):
        call_count = [0]

        def raises_value_error():
            call_count[0] += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            _call_with_retry(raises_value_error, retryable=(ConnectionError,))

        assert call_count[0] == 1

    def test_succeeds_on_second_attempt(self):
        attempt = [0]

        def flaky():
            attempt[0] += 1
            if attempt[0] < 2:
                raise ConnectionError("retry me")
            return "ok"

        with patch("linux_speech_flow.transcription.time.sleep"):
            result = _call_with_retry(flaky, retryable=(ConnectionError,))

        assert result == "ok"
        assert attempt[0] == 2

    def test_passes_args_to_function(self):
        fn = lambda a, b: a + b
        result = _call_with_retry(fn, 3, 4, retryable=(ValueError,))
        assert result == 7

    def test_passes_kwargs_to_function(self):
        fn = lambda x, multiplier=1: x * multiplier
        result = _call_with_retry(fn, 5, retryable=(ValueError,), multiplier=3)
        assert result == 15
