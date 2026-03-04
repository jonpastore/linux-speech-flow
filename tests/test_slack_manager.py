import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linux_speech_flow.slack_manager import SlackManager


@pytest.fixture
def tmp_config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{}")
    return config_path


class TestVerifyToken:
    def test_verify_token_success(self):
        manager = SlackManager()
        with patch("linux_speech_flow.slack_manager.WebClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            ok, err = manager.verify_token("xoxb-valid", "xapp-valid")
        assert ok is True
        assert err == ""
        mock_client.auth_test.assert_called_once()

    def test_verify_token_slack_api_error(self):
        from slack_sdk.errors import SlackApiError
        manager = SlackManager()
        with patch("linux_speech_flow.slack_manager.WebClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.get.return_value = "invalid_auth"
            mock_client.auth_test.side_effect = SlackApiError("error", mock_response)
            mock_client_cls.return_value = mock_client
            ok, err = manager.verify_token("xoxb-bad", "xapp-bad")
        assert ok is False
        assert err == "invalid_auth"

    def test_verify_token_generic_exception(self):
        manager = SlackManager()
        with patch("linux_speech_flow.slack_manager.WebClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.auth_test.side_effect = ConnectionError("network unreachable")
            mock_client_cls.return_value = mock_client
            ok, err = manager.verify_token("xoxb-bad", "xapp-bad")
        assert ok is False
        assert "network unreachable" in err


class TestWorkspaceCRUD:
    def test_add_and_get_workspace(self, tmp_config):
        manager = SlackManager()
        data = {"bot_token": "xoxb-1", "app_token": "xapp-1", "team_name": "TestCo"}
        manager.add_workspace("T001", data, _path=tmp_config)
        result = manager.get_workspaces(_path=tmp_config)
        assert "T001" in result
        assert result["T001"]["team_name"] == "TestCo"

    def test_remove_workspace(self, tmp_config):
        manager = SlackManager()
        data = {"bot_token": "xoxb-1", "app_token": "xapp-1"}
        manager.add_workspace("T001", data, _path=tmp_config)
        manager.remove_workspace("T001", _path=tmp_config)
        result = manager.get_workspaces(_path=tmp_config)
        assert "T001" not in result

    def test_remove_nonexistent_workspace_is_noop(self, tmp_config):
        manager = SlackManager()
        manager.remove_workspace("T_MISSING", _path=tmp_config)

    def test_get_workspaces_empty_returns_dict(self, tmp_config):
        manager = SlackManager()
        result = manager.get_workspaces(_path=tmp_config)
        assert isinstance(result, dict)
        assert result == {}

    def test_add_multiple_workspaces(self, tmp_config):
        manager = SlackManager()
        manager.add_workspace("T001", {"bot_token": "xoxb-1"}, _path=tmp_config)
        manager.add_workspace("T002", {"bot_token": "xoxb-2"}, _path=tmp_config)
        result = manager.get_workspaces(_path=tmp_config)
        assert len(result) == 2
        assert "T001" in result
        assert "T002" in result


class TestPostMessage:
    def test_post_message_success(self, tmp_config):
        manager = SlackManager()
        manager.add_workspace("T001", {"bot_token": "xoxb-1"}, _path=tmp_config)
        with patch("linux_speech_flow.slack_manager.WebClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            result = manager.post_message("T001", "C001", "hello", _path=tmp_config)
        assert result is True
        mock_client.chat_postMessage.assert_called_once_with(channel="C001", text="hello")

    def test_post_message_with_blocks(self, tmp_config):
        manager = SlackManager()
        manager.add_workspace("T001", {"bot_token": "xoxb-1"}, _path=tmp_config)
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}]
        with patch("linux_speech_flow.slack_manager.WebClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            result = manager.post_message("T001", "C001", "hello", blocks=blocks, _path=tmp_config)
        assert result is True
        mock_client.chat_postMessage.assert_called_once_with(channel="C001", text="hello", blocks=blocks)

    def test_post_message_slack_api_error_returns_false(self, tmp_config):
        from slack_sdk.errors import SlackApiError
        manager = SlackManager()
        manager.add_workspace("T001", {"bot_token": "xoxb-1"}, _path=tmp_config)
        with patch("linux_speech_flow.slack_manager.WebClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.get.return_value = "channel_not_found"
            mock_client.chat_postMessage.side_effect = SlackApiError("error", mock_response)
            mock_client_cls.return_value = mock_client
            result = manager.post_message("T001", "C_BAD", "hello", _path=tmp_config)
        assert result is False

    def test_post_message_raises_key_error_unknown_team(self, tmp_config):
        manager = SlackManager()
        with pytest.raises(KeyError):
            manager.post_message("T_UNKNOWN", "C001", "hello", _path=tmp_config)


class TestUploadFile:
    def test_upload_file_success(self, tmp_config, tmp_path):
        manager = SlackManager()
        manager.add_workspace("T001", {"bot_token": "xoxb-1"}, _path=tmp_config)
        fake_file = tmp_path / "audio.wav"
        fake_file.write_bytes(b"RIFF")
        with patch("linux_speech_flow.slack_manager.WebClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            result = manager.upload_file("T001", "C001", str(fake_file), "Huddle Recording", _path=tmp_config)
        assert result is True
        mock_client.files_upload_v2.assert_called_once_with(
            channel="C001",
            file=str(fake_file),
            title="Huddle Recording",
        )

    def test_upload_file_slack_api_error_returns_false(self, tmp_config, tmp_path):
        from slack_sdk.errors import SlackApiError
        manager = SlackManager()
        manager.add_workspace("T001", {"bot_token": "xoxb-1"}, _path=tmp_config)
        with patch("linux_speech_flow.slack_manager.WebClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.get.return_value = "file_upload_failed"
            mock_client.files_upload_v2.side_effect = SlackApiError("error", mock_response)
            mock_client_cls.return_value = mock_client
            result = manager.upload_file("T001", "C001", "/fake/path.wav", "Test", _path=tmp_config)
        assert result is False
