import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from linux_speech_flow.config import load_config, save_config, CONFIG_PATH

logger = logging.getLogger(__name__)


class SlackManager:
    """Manages Slack workspace tokens and API calls.

    Workspaces stored in config.json under slack_workspaces:
    {team_id: {bot_token, app_token, bot_name, channel_id, authed_user_id, team_name}}

    All methods are safe to call from the GTK main thread (blocking I/O is
    acceptable here because verify_token is only called in Settings on user action,
    and post/upload are expected to be called from a worker thread by callers).

    Methods that read/write config accept a keyword-only _path parameter for
    test injection; production code omits it and uses the default CONFIG_PATH.
    """

    def verify_token(self, bot_token: str, app_token: str) -> tuple[bool, str]:
        """Validate bot_token via auth.test. Returns (ok, error_message)."""
        client = WebClient(token=bot_token)
        try:
            client.auth_test()
            return True, ""
        except SlackApiError as exc:
            return False, exc.response.get("error", str(exc))
        except Exception as exc:
            return False, str(exc)

    def add_workspace(self, team_id: str, workspace_data: dict, *, _path=CONFIG_PATH) -> None:
        """Store workspace credentials in config."""
        config = load_config(_path=_path)
        workspaces = dict(config.get("slack_workspaces", {}))
        workspaces[team_id] = workspace_data
        config["slack_workspaces"] = workspaces
        save_config(config, _path=_path)

    def get_workspaces(self, *, _path=CONFIG_PATH) -> dict:
        """Return dict of all stored workspaces."""
        config = load_config(_path=_path)
        return config.get("slack_workspaces", {})

    def remove_workspace(self, team_id: str, *, _path=CONFIG_PATH) -> None:
        """Remove workspace from config."""
        config = load_config(_path=_path)
        workspaces = dict(config.get("slack_workspaces", {}))
        workspaces.pop(team_id, None)
        config["slack_workspaces"] = workspaces
        save_config(config, _path=_path)

    def post_message(self, team_id: str, channel_id: str, text: str, blocks: list | None = None, *, _path=CONFIG_PATH) -> bool:
        """Post a message to a Slack channel. Returns True on success."""
        workspaces = self.get_workspaces(_path=_path)
        token = workspaces[team_id]["bot_token"]
        client = WebClient(token=token)
        try:
            kwargs = {"channel": channel_id, "text": text}
            if blocks:
                kwargs["blocks"] = blocks
            client.chat_postMessage(**kwargs)
            return True
        except SlackApiError as exc:
            logger.error("Slack post_message failed: %s", exc.response.get("error"))
            return False

    def get_channels(self, team_id: str, *, _path=CONFIG_PATH) -> list[tuple[str, str]]:
        """Return list of (channel_id, channel_name) for the workspace, paginated."""
        workspaces = self.get_workspaces(_path=_path)
        token = workspaces.get(team_id, {}).get("bot_token", "")
        if not token:
            return []
        client = WebClient(token=token)
        channels: list[tuple[str, str]] = []
        cursor = None
        try:
            while True:
                resp = client.conversations_list(
                    limit=200,
                    cursor=cursor,
                    types="public_channel,private_channel",
                )
                for ch in resp.get("channels", []):
                    channels.append((ch["id"], ch["name"]))
                cursor = (resp.get("response_metadata") or {}).get("next_cursor")
                if not cursor:
                    break
        except SlackApiError as exc:
            logger.error("get_channels failed: %s", exc.response.get("error"))
        except Exception as exc:
            logger.error("get_channels failed: %s", exc)
        return channels

    def upload_file(self, team_id: str, channel_id: str, file_path: str, title: str, *, _path=CONFIG_PATH) -> bool:
        """Upload a file to a Slack channel. Returns True on success.

        Uses files_upload_v2 (NOT deprecated files.upload which was sunset Nov 2025).
        channel_id must be a channel ID (C-prefix), not a channel name.
        """
        workspaces = self.get_workspaces(_path=_path)
        token = workspaces[team_id]["bot_token"]
        client = WebClient(token=token)
        try:
            client.files_upload_v2(
                channel=channel_id,
                file=file_path,
                title=title,
            )
            return True
        except SlackApiError as exc:
            logger.error("Slack upload_file failed: %s", exc.response.get("error"))
            return False
