from unittest.mock import MagicMock, patch

import requests

from linux_speech_flow.groq_client import validate_api_key

VALID_KEY = "gsk_" + "a" * 50


def test_empty_string_fails_format():
    result = validate_api_key("")
    assert result["ok"] is False
    assert result["message"] == "Invalid API key format"


def test_no_gsk_prefix_fails_format():
    result = validate_api_key("not_groq_key")
    assert result["ok"] is False
    assert result["message"] == "Invalid API key format"


def test_too_short_fails_format():
    short_key = "gsk_" + "x" * 5
    result = validate_api_key(short_key)
    assert result["ok"] is False
    assert result["message"] == "Invalid API key format"


def test_format_fail_makes_no_http_call():
    with patch("linux_speech_flow.groq_client.requests.get") as mock_get:
        validate_api_key("not_groq_key")
        mock_get.assert_not_called()


def test_format_fail_empty_makes_no_http_call():
    with patch("linux_speech_flow.groq_client.requests.get") as mock_get:
        validate_api_key("")
        mock_get.assert_not_called()


def test_format_fail_short_makes_no_http_call():
    with patch("linux_speech_flow.groq_client.requests.get") as mock_get:
        validate_api_key("gsk_" + "x" * 5)
        mock_get.assert_not_called()


def test_valid_format_200_returns_ok():
    mock_response = MagicMock()
    mock_response.status_code = 200
    with patch(
        "linux_speech_flow.groq_client.requests.get", return_value=mock_response
    ):
        result = validate_api_key(VALID_KEY)
    assert result["ok"] is True
    assert "message" not in result


def test_valid_format_401_returns_invalid_key():
    mock_response = MagicMock()
    mock_response.status_code = 401
    with patch(
        "linux_speech_flow.groq_client.requests.get", return_value=mock_response
    ):
        result = validate_api_key(VALID_KEY)
    assert result["ok"] is False
    assert result["message"] == "Invalid API key"


def test_valid_format_500_returns_unexpected():
    mock_response = MagicMock()
    mock_response.status_code = 500
    with patch(
        "linux_speech_flow.groq_client.requests.get", return_value=mock_response
    ):
        result = validate_api_key(VALID_KEY)
    assert result["ok"] is False
    assert "500" in result["message"]


def test_connection_error_returns_connect_message():
    with patch(
        "linux_speech_flow.groq_client.requests.get",
        side_effect=requests.exceptions.ConnectionError(),
    ):
        result = validate_api_key(VALID_KEY)
    assert result["ok"] is False
    assert "connect" in result["message"].lower()


def test_timeout_returns_connect_message():
    with patch(
        "linux_speech_flow.groq_client.requests.get",
        side_effect=requests.exceptions.Timeout(),
    ):
        result = validate_api_key(VALID_KEY)
    assert result["ok"] is False
    assert "connect" in result["message"].lower()


def test_http_call_uses_correct_url_and_header():
    mock_response = MagicMock()
    mock_response.status_code = 200
    with patch(
        "linux_speech_flow.groq_client.requests.get", return_value=mock_response
    ) as mock_get:
        validate_api_key(VALID_KEY)
    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert call_args[0][0] == "https://api.groq.com/openai/v1/models"
    assert call_args[1]["headers"]["Authorization"] == f"Bearer {VALID_KEY}"
    assert call_args[1]["timeout"] == 10
