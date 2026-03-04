import logging
import threading
from gi.repository import GLib
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.web import WebClient

logger = logging.getLogger(__name__)


class SlackSocket:
    """SocketModeClient wrapper for Slack huddle event detection.

    Runs SocketModeClient.connect() in a daemon thread.
    Never calls start() — it blocks the calling thread.
    All GTK callbacks dispatched via GLib.idle_add.
    """

    def __init__(self):
        self._client: SocketModeClient | None = None

    def start(
        self,
        app_token: str,
        bot_token: str,
        on_huddle_event,
        on_huddle_end,
        authed_user_id: str,
    ) -> None:
        """Connect to Slack Socket Mode in a daemon thread."""
        self._client = SocketModeClient(
            app_token=app_token,
            web_client=WebClient(token=bot_token),
        )
        self._client.socket_mode_request_listeners.append(
            self._make_listener(on_huddle_event, on_huddle_end, authed_user_id)
        )
        threading.Thread(
            target=self._client.connect,
            daemon=True,
            name="slack-socket-mode",
        ).start()
        logger.info("SlackSocket: connecting via Socket Mode (daemon thread)")

    def stop(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def _make_listener(self, on_huddle_event, on_huddle_end, authed_user_id: str):
        def listener(client: SocketModeClient, req):
            try:
                if req.type == "events_api":
                    payload = req.payload or {}
                    event = payload.get("event", {})
                    if event.get("type") == "user_huddle_changed":
                        event_user = event.get("user", {})
                        user_id = event_user.get("id") if isinstance(event_user, dict) else event_user
                        if user_id == authed_user_id:
                            event_user_dict = event_user if isinstance(event_user, dict) else {}
                            is_active = event_user_dict.get("is_huddle_active", True)
                            if not is_active:
                                GLib.idle_add(on_huddle_end)
                            else:
                                GLib.idle_add(on_huddle_event, event)
                        else:
                            logger.debug(
                                "Ignoring huddle event for user %s (not authed user)", user_id
                            )
            finally:
                client.send_socket_mode_response(
                    SocketModeResponse(envelope_id=req.envelope_id)
                )
        return listener
