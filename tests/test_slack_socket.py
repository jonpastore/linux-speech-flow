"""Tests for SlackSocket in slack_socket.py."""
import threading
from unittest.mock import MagicMock, patch, call


def test_slack_socket_connect_in_daemon_thread():
    """SlackSocket.start() calls SocketModeClient.connect() in a daemon thread."""
    from linux_speech_flow.slack_socket import SlackSocket

    with patch("linux_speech_flow.slack_socket.SocketModeClient") as MockClient, patch(
        "linux_speech_flow.slack_socket.WebClient"
    ), patch("linux_speech_flow.slack_socket.threading") as mock_threading:

        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        mock_client_instance.socket_mode_request_listeners = []

        mock_thread = MagicMock()
        mock_threading.Thread.return_value = mock_thread

        sock = SlackSocket()
        sock.start("xapp-token", "xoxb-token", MagicMock(), MagicMock(), "U123")

        mock_threading.Thread.assert_called_once()
        call_kwargs = mock_threading.Thread.call_args
        assert call_kwargs.kwargs.get("daemon") is True or (
            len(call_kwargs.args) > 0 and False
        ), "daemon=True required"
        mock_thread.start.assert_called_once()


def test_slack_socket_connect_called_as_target():
    """The thread target is client.connect (not client.start which blocks)."""
    from linux_speech_flow.slack_socket import SlackSocket

    with patch("linux_speech_flow.slack_socket.SocketModeClient") as MockClient, patch(
        "linux_speech_flow.slack_socket.WebClient"
    ), patch("linux_speech_flow.slack_socket.threading") as mock_threading:

        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        mock_client_instance.socket_mode_request_listeners = []

        mock_thread = MagicMock()
        mock_threading.Thread.return_value = mock_thread

        sock = SlackSocket()
        sock.start("xapp-token", "xoxb-token", MagicMock(), MagicMock(), "U123")

        call_kwargs = mock_threading.Thread.call_args
        assert call_kwargs.kwargs.get("target") == mock_client_instance.connect


def _make_huddle_event(user_id: str, is_huddle_active: bool) -> dict:
    return {
        "type": "events_api",
        "payload": {
            "event": {
                "type": "user_huddle_changed",
                "user": {
                    "id": user_id,
                    "is_huddle_active": is_huddle_active,
                },
            }
        },
        "envelope_id": "env-001",
    }


def _make_req(event_dict: dict):
    req = MagicMock()
    req.type = event_dict["type"]
    req.payload = event_dict["payload"]
    req.envelope_id = event_dict["envelope_id"]
    return req


def test_listener_fires_on_huddle_event_for_authed_user():
    """Active huddle event for authed user -> on_huddle_event called via GLib.idle_add."""
    from linux_speech_flow.slack_socket import SlackSocket

    with patch("linux_speech_flow.slack_socket.GLib") as mock_glib:
        sock = SlackSocket()
        on_huddle = MagicMock()
        on_end = MagicMock()
        listener = sock._make_listener(on_huddle, on_end, "U123")

        req = _make_req(_make_huddle_event("U123", True))
        mock_client = MagicMock()
        listener(mock_client, req)

        mock_glib.idle_add.assert_called_once()
        args = mock_glib.idle_add.call_args[0]
        assert args[0] == on_huddle
        on_end.assert_not_called()


def test_listener_fires_on_huddle_end_when_inactive():
    """Inactive huddle event for authed user -> on_huddle_end called via GLib.idle_add."""
    from linux_speech_flow.slack_socket import SlackSocket

    with patch("linux_speech_flow.slack_socket.GLib") as mock_glib:
        sock = SlackSocket()
        on_huddle = MagicMock()
        on_end = MagicMock()
        listener = sock._make_listener(on_huddle, on_end, "U123")

        req = _make_req(_make_huddle_event("U123", False))
        mock_client = MagicMock()
        listener(mock_client, req)

        mock_glib.idle_add.assert_called_once_with(on_end)
        on_huddle.assert_not_called()


def test_listener_ignores_non_authed_user():
    """Huddle event for different user -> neither callback called."""
    from linux_speech_flow.slack_socket import SlackSocket

    with patch("linux_speech_flow.slack_socket.GLib") as mock_glib:
        sock = SlackSocket()
        on_huddle = MagicMock()
        on_end = MagicMock()
        listener = sock._make_listener(on_huddle, on_end, "U123")

        req = _make_req(_make_huddle_event("U999", True))
        mock_client = MagicMock()
        listener(mock_client, req)

        mock_glib.idle_add.assert_not_called()
        on_huddle.assert_not_called()
        on_end.assert_not_called()


def test_listener_ignores_non_huddle_event():
    """Non-huddle event type -> on_huddle_event NOT called."""
    from linux_speech_flow.slack_socket import SlackSocket

    with patch("linux_speech_flow.slack_socket.GLib") as mock_glib:
        sock = SlackSocket()
        on_huddle = MagicMock()
        on_end = MagicMock()
        listener = sock._make_listener(on_huddle, on_end, "U123")

        req = MagicMock()
        req.type = "events_api"
        req.payload = {"event": {"type": "message", "text": "hello"}}
        req.envelope_id = "env-002"

        mock_client = MagicMock()
        listener(mock_client, req)

        mock_glib.idle_add.assert_not_called()
        on_huddle.assert_not_called()


def test_listener_always_acks():
    """SocketModeResponse ACK always sent, even for non-huddle events."""
    from linux_speech_flow.slack_socket import SlackSocket
    from slack_sdk.socket_mode.response import SocketModeResponse

    with patch("linux_speech_flow.slack_socket.GLib"):
        sock = SlackSocket()
        listener = sock._make_listener(MagicMock(), MagicMock(), "U123")

        req = MagicMock()
        req.type = "events_api"
        req.payload = {"event": {"type": "message"}}
        req.envelope_id = "env-003"

        mock_client = MagicMock()
        listener(mock_client, req)

        mock_client.send_socket_mode_response.assert_called_once()
        sent_resp = mock_client.send_socket_mode_response.call_args[0][0]
        assert sent_resp.envelope_id == "env-003"


def test_listener_acks_even_for_active_huddle():
    """ACK sent even when on_huddle_event is triggered."""
    from linux_speech_flow.slack_socket import SlackSocket

    with patch("linux_speech_flow.slack_socket.GLib"):
        sock = SlackSocket()
        on_huddle = MagicMock()
        on_end = MagicMock()
        listener = sock._make_listener(on_huddle, on_end, "U123")

        req = _make_req(_make_huddle_event("U123", True))
        mock_client = MagicMock()
        listener(mock_client, req)

        mock_client.send_socket_mode_response.assert_called_once()
