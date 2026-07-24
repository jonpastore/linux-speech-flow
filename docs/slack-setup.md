# Slack Setup Guide

linux-speech-flow can post transcriptions to Slack channels and record Slack
huddle sessions. This needs a **Slack app** with two tokens:

- a **Bot User OAuth Token** (`xoxb-…`) — posts messages and lists channels
- an **App-Level Token** (`xapp-…`) — connects over Socket Mode to detect huddles

You create both once, then paste them into **Settings → Integrations → Add
Workspace**. No public URL or hosting is required (Socket Mode connects outward).

---

## 1. Create the app

1. Go to <https://api.slack.com/apps> and click **Create New App → From scratch**.
2. Name it (e.g. `linux-speech-flow`) and pick your workspace. Click **Create App**.

## 2. Add bot scopes

1. In the left sidebar open **OAuth & Permissions**.
2. Under **Scopes → Bot Token Scopes**, add:
   - `chat:write` — post transcriptions
   - `channels:read` — list public channels
   - `groups:read` — list private channels the bot is in
3. (Leave User Token Scopes empty — the app only uses a bot token.)

## 3. Enable Socket Mode + create the app-level token

1. In the sidebar open **Socket Mode** and toggle **Enable Socket Mode** on.
2. When prompted, create an **App-Level Token** with the `connections:write`
   scope (name it e.g. `socket`). Copy the `xapp-…` value now — you'll paste it
   in later. (You can also create it under **Basic Information → App-Level Tokens**.)

## 4. Subscribe to events (for huddle detection)

1. In the sidebar open **Event Subscriptions** and toggle **Enable Events** on.
2. Under **Subscribe to bot events**, add `user_huddle_changed` (huddle
   start/stop detection). Save changes.

## 5. Install to your workspace

1. Back on **OAuth & Permissions**, click **Install to Workspace** and **Allow**.
2. Copy the **Bot User OAuth Token** (`xoxb-…`) shown after install.
3. Invite the bot to any channel you want transcriptions posted to: in Slack,
   `/invite @linux-speech-flow` in that channel.

## 6. Connect it in the app

1. Open linux-speech-flow **Settings → Integrations → Add Workspace**.
2. Paste the **Bot User OAuth Token** (`xoxb-…`) and the **App-Level Token**
   (`xapp-…`). The app validates them (`auth.test`) and connects Socket Mode.
3. Pick a default channel for transcriptions if prompted.

Tokens are stored in `~/.config/linux-speech-flow/config.json` (mode `0600`,
readable only by you). To revoke, delete the workspace in Settings or uninstall
the app from your Slack workspace's **Manage Apps** page.

---

## Troubleshooting

- **`invalid_auth` / `not_authed`** — the bot token is wrong or the app was
  uninstalled. Reinstall (step 5) and re-copy the `xoxb-…` token.
- **Bot can't post to a channel** — it isn't a member; `/invite` it there.
- **Huddles not detected** — confirm Socket Mode is enabled, the app-level token
  has `connections:write`, and `user_huddle_changed` is subscribed (steps 3–4).
- **Private channels missing from the list** — add `groups:read` and reinstall,
  and make sure the bot is a member of the private channel.
