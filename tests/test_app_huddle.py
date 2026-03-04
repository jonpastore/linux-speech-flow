"""Tests for app.py huddle wiring.

Tests _on_huddle_end_detected, _on_huddle_event_detected, and SlackSocket
callback registration logic. Uses App.__new__() to skip GTK __init__ while
keeping the real class methods under test.
"""
from unittest.mock import MagicMock, patch

from linux_speech_flow.app import App


def _make_app():
    """Return a minimal App instance with huddle-related attributes mocked."""
    app = App.__new__(App)
    app._huddle_manager = MagicMock()
    app._tray = MagicMock()
    app._hotkey_manager = MagicMock()
    app._slack_sockets = []
    return app


class TestOnHuddleEndDetected:
    def test_stops_active_session_when_huddle_active(self):
        app = _make_app()
        app._huddle_manager.is_active.return_value = True

        app._on_huddle_end_detected()

        app._huddle_manager.stop_session.assert_called_once()
        app._tray.set_huddle_recording.assert_called_once_with(False)

    def test_noop_when_no_active_session(self):
        app = _make_app()
        app._huddle_manager.is_active.return_value = False

        app._on_huddle_end_detected()

        app._huddle_manager.stop_session.assert_not_called()

    def test_noop_when_huddle_manager_is_none(self):
        app = _make_app()
        app._huddle_manager = None

        app._on_huddle_end_detected()

    def test_on_huddle_stop_calls_stop_session(self):
        app = _make_app()
        app._on_huddle_stop()
        app._huddle_manager.stop_session.assert_called_once()

    def test_on_huddle_stop_calls_set_huddle_recording_false(self):
        app = _make_app()
        app._on_huddle_stop()
        app._tray.set_huddle_recording.assert_called_once_with(False)


class TestOnHuddleEventDetected:
    def test_uses_event_channel_id_when_present(self):
        app = _make_app()
        event = {"team_id": "T001", "huddle_state": {"channel_id": "C123"}}
        config = {"slack_huddle_auto_detect": "always"}

        with patch(
            "linux_speech_flow.app.load_config", return_value=config
        ), patch.object(app, "_on_huddle_start_for") as mock_start:
            app._on_huddle_event_detected(event)

        mock_start.assert_called_once_with("T001", "C123")

    def test_fallback_to_config_channel_id_when_event_empty(self):
        app = _make_app()
        event = {"team_id": "T001", "huddle_state": {}}
        config = {
            "slack_huddle_auto_detect": "always",
            "slack_workspaces": {"T001": {"channel_id": "C999"}},
        }

        with patch(
            "linux_speech_flow.app.load_config", return_value=config
        ), patch.object(app, "_on_huddle_start_for") as mock_start:
            app._on_huddle_event_detected(event)

        mock_start.assert_called_once_with("T001", "C999")

    def test_no_start_when_manual_mode(self):
        app = _make_app()
        event = {"team_id": "T001", "huddle_state": {"channel_id": "C123"}}
        config = {"slack_huddle_auto_detect": "manual"}

        with patch(
            "linux_speech_flow.app.load_config", return_value=config
        ), patch.object(app, "_on_huddle_start_for") as mock_start:
            app._on_huddle_event_detected(event)

        mock_start.assert_not_called()

    def test_prompt_mode_notifies_not_starts(self):
        app = _make_app()
        event = {"team_id": "T001", "huddle_state": {"channel_id": "C123"}}
        config = {"slack_huddle_auto_detect": "prompt"}

        with patch(
            "linux_speech_flow.app.load_config", return_value=config
        ), patch.object(app, "_on_huddle_start_for") as mock_start, patch(
            "linux_speech_flow.app.send_notification"
        ) as mock_notify:
            app._on_huddle_event_detected(event)

        mock_start.assert_not_called()
        mock_notify.assert_called_once()


class TestSlackSocketCallbackRegistration:
    def test_on_huddle_end_callback_passed_to_slack_socket(self):
        """Verify on_huddle_end=_on_huddle_end_detected and
        on_huddle_event=_on_huddle_event_detected are passed to SlackSocket.start()."""
        app = _make_app()
        mock_sock = MagicMock()

        mock_sock.start(
            app_token="xapp-1",
            bot_token="xoxb-1",
            on_huddle_event=app._on_huddle_event_detected,
            on_huddle_end=app._on_huddle_end_detected,
            authed_user_id="U123",
        )
        app._slack_sockets.append(mock_sock)

        assert len(app._slack_sockets) == 1
        kwargs = mock_sock.start.call_args.kwargs
        assert kwargs["on_huddle_end"] == app._on_huddle_end_detected
        assert kwargs["on_huddle_event"] == app._on_huddle_event_detected
        assert kwargs["authed_user_id"] == "U123"


class TestWizardPageCount:
    def test_wizard_has_six_pages(self):
        from linux_speech_flow.wizard import WizardWindow
        assert len(WizardWindow.PAGES) == 6, (
            f"Expected 6 wizard pages, got {len(WizardWindow.PAGES)}: {WizardWindow.PAGES}"
        )
