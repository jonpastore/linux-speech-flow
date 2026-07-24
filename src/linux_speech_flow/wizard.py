import math

TECH_STACKS = {
    "Go / Golang": [
        "Go",
        "Golang",
        "goroutine",
        "goroutines",
        "gRPC",
        "protobuf",
        "proto",
        "GOPATH",
        "go.mod",
        "go.sum",
        "golangci-lint",
        "Gopher",
        "defer",
        "chan",
    ],
    "Python": [
        "Python",
        "PyPI",
        "pip",
        "venv",
        "virtualenv",
        "Django",
        "Flask",
        "FastAPI",
        "SQLAlchemy",
        "Pydantic",
        "pytest",
        "asyncio",
        "Celery",
        "NumPy",
        "pandas",
        "PyGObject",
        "pyproject.toml",
        "Jupyter",
    ],
    "Rust": [
        "Rust",
        "Cargo",
        "crate",
        "crates.io",
        "Tokio",
        "Actix",
        "Serde",
        "rustup",
        "rustfmt",
        "Clippy",
        "borrow checker",
        "lifetime",
        "ownership",
        "unsafe",
    ],
    "JavaScript / TypeScript": [
        "JavaScript",
        "TypeScript",
        "Node.js",
        "npm",
        "yarn",
        "pnpm",
        "Webpack",
        "Vite",
        "ESLint",
        "Prettier",
        "React",
        "Vue",
        "Svelte",
        "Next.js",
        "Bun",
        "Deno",
        "Jest",
        "Vitest",
        "tsconfig",
    ],
    "DevOps / CI-CD": [
        "DevOps",
        "CI/CD",
        "GitHub Actions",
        "GitLab CI",
        "Jenkins",
        "Terraform",
        "Ansible",
        "Helm",
        "ArgoCD",
        "FluxCD",
        "pipeline",
        "artifact",
        "canary",
        "blue-green",
        "rollback",
    ],
    "Kubernetes / Docker": [
        "Kubernetes",
        "kubectl",
        "Helm",
        "pod",
        "namespace",
        "deployment",
        "ingress",
        "ConfigMap",
        "StatefulSet",
        "DaemonSet",
        "ReplicaSet",
        "etcd",
        "Docker",
        "Dockerfile",
        "docker-compose",
        "containerd",
    ],
    "AWS": [
        "AWS",
        "EC2",
        "S3",
        "IAM",
        "Lambda",
        "CloudFormation",
        "VPC",
        "EKS",
        "ECS",
        "RDS",
        "DynamoDB",
        "CloudFront",
        "Route 53",
        "SQS",
        "SNS",
        "CloudWatch",
    ],
    "GCP": [
        "GCP",
        "Google Cloud",
        "GKE",
        "Cloud Run",
        "BigQuery",
        "Pub/Sub",
        "Cloud Storage",
        "Cloud Functions",
        "Cloud SQL",
        "Firestore",
        "Vertex AI",
        "Artifact Registry",
        "Cloud Build",
        "gcloud",
    ],
    "Azure": [
        "Azure",
        "AKS",
        "Azure DevOps",
        "Azure Functions",
        "Blob Storage",
        "Cosmos DB",
        "Azure SQL",
        "App Service",
        "Entra ID",
        "Bicep",
        "Service Bus",
        "Event Hub",
    ],
    "PostgreSQL": [
        "PostgreSQL",
        "Postgres",
        "psql",
        "pg_dump",
        "pg_restore",
        "PostGIS",
        "VACUUM",
        "ANALYZE",
        "JSONB",
        "CTE",
        "upsert",
        "COALESCE",
        "pgAdmin",
    ],
    "MySQL / MariaDB": [
        "MySQL",
        "MariaDB",
        "mysqldump",
        "InnoDB",
        "EXPLAIN",
        "stored procedure",
        "replication",
        "binlog",
        "Galera",
        "Percona",
    ],
    "Linux / Systems": [
        "systemd",
        "journalctl",
        "crontab",
        "iptables",
        "nftables",
        "nginx",
        "OpenSSL",
        "rsync",
        "strace",
        "lsof",
        "tcpdump",
        "POSIX",
        "daemon",
    ],
    "Security / Auth": [
        "OAuth",
        "OAuth 2.0",
        "OIDC",
        "JWT",
        "SAML",
        "SSO",
        "MFA",
        "TOTP",
        "bcrypt",
        "argon2",
        "TLS",
        "mTLS",
        "RBAC",
        "CSRF",
        "XSS",
        "OWASP",
        "Vault",
        "Keycloak",
    ],
}
import struct
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
import pulsectl
from gi.repository import GLib, Gtk

from linux_speech_flow.audio import list_microphones
from linux_speech_flow.config import load_config, save_config
from linux_speech_flow.groq_client import validate_api_key


def _block_scroll(combo: Gtk.ComboBoxText) -> None:
    ctrl = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
    ctrl.connect("scroll", lambda _c, _dx, _dy: True)
    combo.add_controller(ctrl)


class WizardWindow(Gtk.ApplicationWindow):
    PAGES = [
        "provider",
        "api_key",
        "grok_key",
        "gemini_key",
        "litellm",
        "slack_key",
        "microphone",
        "vocabulary",
    ]

    def __init__(self, application, config: dict | None = None):
        super().__init__(application=application, title="linux-speech-flow Setup")
        self._config = config if config is not None else load_config()
        self._api_key_valid = False
        self._provider_mode = self._config.get("provider_mode", "cloud")
        self._current_page = 0
        self._mics = []

        self.set_default_size(480, 360)
        self.set_resizable(False)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._stack.set_vexpand(True)
        outer.append(self._stack)

        self._stack.add_named(self._build_provider_page(), "provider")
        self._stack.add_named(self._build_api_key_page(), "api_key")
        self._stack.add_named(self._build_grok_key_page(), "grok_key")
        self._stack.add_named(self._build_gemini_key_page(), "gemini_key")
        self._stack.add_named(self._build_litellm_page(), "litellm")
        self._stack.add_named(self._build_slack_key_page(), "slack_key")
        self._stack.add_named(self._build_microphone_page(), "microphone")
        self._stack.add_named(self._build_vocabulary_page(), "vocabulary")
        self._stack.set_visible_child_name("provider")

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        nav.set_margin_start(12)
        nav.set_margin_end(12)
        nav.set_margin_top(8)
        nav.set_margin_bottom(12)
        outer.append(nav)

        self._back_btn = Gtk.Button(label="Back")
        self._back_btn.connect("clicked", self._on_back)
        self._back_btn.set_sensitive(False)
        nav.append(self._back_btn)

        self._progress_label = Gtk.Label(label="")
        self._progress_label.add_css_class("dim-label")
        self._progress_label.set_hexpand(True)
        nav.append(self._progress_label)

        self._next_btn = Gtk.Button(label="Next")
        self._next_btn.connect("clicked", self._on_next)
        self._next_btn.add_css_class("suggested-action")
        nav.append(self._next_btn)

        self._update_navigation()

    def _build_provider_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(12)

        title = Gtk.Label(label="How do you want to connect?")
        title.add_css_class("title-2")
        title.set_xalign(0)
        box.append(title)

        desc = Gtk.Label(
            label="Choose how transcription and conversation analysis are routed."
        )
        desc.set_xalign(0)
        desc.set_wrap(True)
        box.append(desc)

        self._provider_cloud_radio = Gtk.CheckButton(
            label="Cloud APIs (Groq/Grok/Gemini keys)"
        )
        self._provider_litellm_radio = Gtk.CheckButton(
            label="Local LiteLLM endpoint (free, self-hosted)"
        )
        self._provider_litellm_radio.set_group(self._provider_cloud_radio)
        if self._provider_mode == "litellm":
            self._provider_litellm_radio.set_active(True)
        else:
            self._provider_cloud_radio.set_active(True)
        # Connect BOTH radios: on a grouped toggle GTK fires the deactivating
        # button's handler before the activating one's `active` flips true, so a
        # handler on only the cloud radio reads a stale state and never sees
        # "litellm". Both connected → the last-firing handler settles the mode.
        self._provider_cloud_radio.connect("toggled", self._on_provider_changed)
        self._provider_litellm_radio.connect("toggled", self._on_provider_changed)
        box.append(self._provider_cloud_radio)
        box.append(self._provider_litellm_radio)

        return box

    def _on_provider_changed(self, _btn):
        self._provider_mode = (
            "litellm" if self._provider_litellm_radio.get_active() else "cloud"
        )

    def _build_litellm_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(12)

        title = Gtk.Label(label="Local LiteLLM Endpoint")
        title.add_css_class("title-2")
        title.set_xalign(0)
        box.append(title)

        desc = Gtk.Label(
            label="OpenAI-compatible endpoint used for both transcription and analysis."
        )
        desc.set_xalign(0)
        desc.set_wrap(True)
        box.append(desc)

        url_label = Gtk.Label(label="Base URL")
        url_label.set_xalign(0)
        box.append(url_label)
        self._litellm_url_entry = Gtk.Entry()
        self._litellm_url_entry.set_text(
            self._config.get("litellm_base_url", "http://cerberus-ai:4000/v1")
        )
        box.append(self._litellm_url_entry)

        key_label = Gtk.Label(label="API key")
        key_label.set_xalign(0)
        box.append(key_label)
        self._litellm_key_entry = Gtk.PasswordEntry()
        self._litellm_key_entry.set_show_peek_icon(True)
        if self._config.get("litellm_api_key"):
            self._litellm_key_entry.set_text(self._config["litellm_api_key"])
        box.append(self._litellm_key_entry)

        whisper_label = Gtk.Label(label="Whisper model")
        whisper_label.set_xalign(0)
        box.append(whisper_label)
        self._litellm_whisper_entry = Gtk.Entry()
        self._litellm_whisper_entry.set_text(
            self._config.get("litellm_whisper_model", "whisper-turbo")
        )
        box.append(self._litellm_whisper_entry)

        chat_label = Gtk.Label(label="Chat model")
        chat_label.set_xalign(0)
        box.append(chat_label)
        self._litellm_chat_entry = Gtk.Entry()
        self._litellm_chat_entry.set_text(
            self._config.get("litellm_chat_model", "gpt-oss-120b-think")
        )
        box.append(self._litellm_chat_entry)

        test_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        test_btn = Gtk.Button(label="Test connection")
        test_btn.connect("clicked", self._on_test_litellm)
        test_row.append(test_btn)
        self._litellm_spinner = Gtk.Spinner()
        test_row.append(self._litellm_spinner)
        box.append(test_row)

        self._litellm_status = Gtk.Label(label="")
        self._litellm_status.set_xalign(0)
        self._litellm_status.set_wrap(True)
        box.append(self._litellm_status)

        return box

    def _on_test_litellm(self, _btn):
        base_url = self._litellm_url_entry.get_text().strip().rstrip("/")
        key = self._litellm_key_entry.get_text().strip()
        self._litellm_status.set_text("")
        self._litellm_spinner.start()

        def run():
            import requests

            try:
                resp = requests.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=10,
                )
                ok = resp.status_code == 200
                msg = "✓ Connection OK" if ok else f"Failed — HTTP {resp.status_code}"
                GLib.idle_add(self._on_test_litellm_done, ok, msg)
            except Exception as exc:
                GLib.idle_add(self._on_test_litellm_done, False, f"Failed — {exc}")
            return False

        threading.Thread(target=run, daemon=True).start()

    def _on_test_litellm_done(self, ok: bool, message: str):
        self._litellm_spinner.stop()
        self._litellm_status.remove_css_class("error")
        self._litellm_status.remove_css_class("success")
        self._litellm_status.add_css_class("success" if ok else "error")
        self._litellm_status.set_text(message)
        return False

    def _build_api_key_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(12)

        title = Gtk.Label(label="Groq API Key")
        title.add_css_class("title-2")
        title.set_xalign(0)
        box.append(title)

        desc = Gtk.Label(label="Enter your Groq API key. Get one at console.groq.com.")
        desc.set_xalign(0)
        desc.set_wrap(True)
        box.append(desc)

        self._api_key_entry = Gtk.PasswordEntry()
        self._api_key_entry.set_show_peek_icon(True)
        self._api_key_entry.set_property("placeholder-text", "gsk_...")
        box.append(self._api_key_entry)

        validate_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._validate_btn = Gtk.Button(label="Validate")
        self._validate_btn.connect("clicked", self._on_validate_api_key)
        validate_row.append(self._validate_btn)

        self._spinner = Gtk.Spinner()
        validate_row.append(self._spinner)
        box.append(validate_row)

        self._api_key_error = Gtk.Label(label="")
        self._api_key_error.set_xalign(0)
        self._api_key_error.set_wrap(True)
        self._api_key_error.add_css_class("error")
        box.append(self._api_key_error)

        self._api_key_success = Gtk.Label(label="")
        self._api_key_success.set_xalign(0)
        self._api_key_success.add_css_class("success")
        box.append(self._api_key_success)

        if self._config.get("groq_api_key"):
            self._api_key_entry.set_text(self._config["groq_api_key"])
            self._api_key_valid = True
            self._api_key_success.set_text("✓ API key valid")

        return box

    def _build_grok_key_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(12)

        title = Gtk.Label(label="Grok API Key (optional)")
        title.add_css_class("title-2")
        title.set_xalign(0)
        box.append(title)

        desc = Gtk.Label(
            label="Required only for conversation analysis with Grok by xAI."
        )
        desc.set_xalign(0)
        desc.set_wrap(True)
        box.append(desc)

        self._grok_key_entry = Gtk.PasswordEntry()
        self._grok_key_entry.set_show_peek_icon(True)
        self._grok_key_entry.set_property("placeholder-text", "xai-...")
        box.append(self._grok_key_entry)

        link = Gtk.Label()
        link.set_markup(
            '<a href="https://console.x.ai/">Get API key at console.x.ai</a>'
        )
        link.set_xalign(0)
        box.append(link)

        if self._config.get("grok_api_key"):
            self._grok_key_entry.set_text(self._config["grok_api_key"])

        self._grok_validate_label = Gtk.Label(label="")
        self._grok_validate_label.set_xalign(0)
        box.append(self._grok_validate_label)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        validate_btn = Gtk.Button(label="Validate")
        validate_btn.connect("clicked", self._on_validate_grok)
        btn_row.append(validate_btn)
        skip_btn = Gtk.Button(label="Skip")
        skip_btn.connect(
            "clicked",
            lambda _: (self._grok_key_entry.set_text(""), self._on_next(None)),
        )
        btn_row.append(skip_btn)
        box.append(btn_row)

        return box

    def _on_validate_grok(self, _btn):
        key = self._grok_key_entry.get_text().strip()
        if not key:
            self._grok_validate_label.set_text("Enter a key first.")
        elif key.startswith("xai-"):
            self._grok_validate_label.set_text("Format OK")
        else:
            self._grok_validate_label.set_text("Invalid — expected xai-... prefix")

    def _build_gemini_key_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(12)

        title = Gtk.Label(label="Gemini API Key (optional)")
        title.add_css_class("title-2")
        title.set_xalign(0)
        box.append(title)

        desc = Gtk.Label(
            label="Required only for conversation analysis with Google Gemini."
        )
        desc.set_xalign(0)
        desc.set_wrap(True)
        box.append(desc)

        self._gemini_key_entry = Gtk.PasswordEntry()
        self._gemini_key_entry.set_show_peek_icon(True)
        self._gemini_key_entry.set_property("placeholder-text", "AI...")
        box.append(self._gemini_key_entry)

        link = Gtk.Label()
        link.set_markup(
            '<a href="https://aistudio.google.com/apikey">Get API key at aistudio.google.com</a>'
        )
        link.set_xalign(0)
        box.append(link)

        if self._config.get("gemini_api_key"):
            self._gemini_key_entry.set_text(self._config["gemini_api_key"])

        self._gemini_validate_label = Gtk.Label(label="")
        self._gemini_validate_label.set_xalign(0)
        box.append(self._gemini_validate_label)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        validate_btn = Gtk.Button(label="Validate")
        validate_btn.connect("clicked", self._on_validate_gemini)
        btn_row.append(validate_btn)
        skip_btn = Gtk.Button(label="Skip")
        skip_btn.connect(
            "clicked",
            lambda _: (self._gemini_key_entry.set_text(""), self._on_next(None)),
        )
        btn_row.append(skip_btn)
        box.append(btn_row)

        return box

    def _on_validate_gemini(self, _btn):
        key = self._gemini_key_entry.get_text().strip()
        if not key:
            self._gemini_validate_label.set_text("Enter a key first.")
        elif len(key) > 10:
            self._gemini_validate_label.set_text("Format OK")
        else:
            self._gemini_validate_label.set_text("Key too short — check your key")

    def _build_slack_key_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(12)

        title = Gtk.Label(label="Slack Integration (optional)")
        title.add_css_class("title-2")
        title.set_xalign(0)
        box.append(title)

        desc = Gtk.Label(
            label=(
                "Slack integration lets linux-speech-flow post transcriptions to Slack "
                "and record Slack huddle sessions.\n\n"
                "Slack requires creating a Slack App with a bot token and an app-level token — "
                "see docs/slack-setup.md for the step-by-step guide. You can connect Slack at "
                "any time via Settings > Integrations."
            )
        )
        desc.set_xalign(0)
        desc.set_wrap(True)
        box.append(desc)

        link = Gtk.Label()
        link.set_markup(
            '<a href="https://api.slack.com/apps">Create a Slack App at api.slack.com</a>'
        )
        link.set_xalign(0)
        box.append(link)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        validate_btn = Gtk.Button(label="Validate")
        validate_btn.connect("clicked", lambda _: None)
        validate_btn.set_sensitive(False)
        validate_btn.set_tooltip_text(
            "Slack setup must be completed via Settings > Integrations after wizard"
        )
        btn_row.append(validate_btn)
        skip_btn = Gtk.Button(label="Skip")
        skip_btn.connect("clicked", lambda _: self._on_next(None))
        btn_row.append(skip_btn)
        box.append(btn_row)

        return box

    def _build_microphone_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(12)

        title = Gtk.Label(label="Microphone")
        title.add_css_class("title-2")
        title.set_xalign(0)
        box.append(title)

        desc = Gtk.Label(label="Select the microphone to use for speech recognition.")
        desc.set_xalign(0)
        desc.set_wrap(True)
        box.append(desc)

        self._mic_combo = Gtk.ComboBoxText()
        self._mic_combo.connect("changed", self._on_mic_changed)
        _block_scroll(self._mic_combo)
        box.append(self._mic_combo)

        vu_label = Gtk.Label(label="Input level:")
        vu_label.set_xalign(0)
        vu_label.set_margin_top(8)
        box.append(vu_label)

        self._vu_bar = Gtk.LevelBar()
        self._vu_bar.set_min_value(0.0)
        self._vu_bar.set_max_value(1.0)
        self._vu_bar.set_value(0.0)
        self._vu_bar.set_margin_bottom(4)
        box.append(self._vu_bar)

        vu_hint = Gtk.Label(
            label="Speak to confirm your microphone is picking up audio."
        )
        vu_hint.set_xalign(0)
        vu_hint.set_wrap(True)
        vu_hint.add_css_class("dim-label")
        box.append(vu_hint)

        self._mic_error = Gtk.Label(label="")
        self._mic_error.set_xalign(0)
        self._mic_error.set_wrap(True)
        self._mic_error.add_css_class("error")
        box.append(self._mic_error)

        return box

    def _build_vocabulary_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(12)

        title = Gtk.Label(label="Vocabulary (optional)")
        title.add_css_class("title-2")
        title.set_xalign(0)
        box.append(title)

        desc = Gtk.Label(
            label="Whisper often misspells technical names, product names, and jargon. "
            "Words listed here are included in every transcription prompt so they "
            "are spelled exactly as you enter them. One word or phrase per line."
        )
        desc.set_xalign(0)
        desc.set_wrap(True)
        box.append(desc)

        # Tech stack preset row
        stack_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        stack_row.set_margin_top(4)

        stack_label = Gtk.Label(label="Add preset:")
        stack_label.set_xalign(0)
        stack_row.append(stack_label)

        self._stack_combo = Gtk.ComboBoxText()
        self._stack_combo.set_hexpand(True)
        for name in TECH_STACKS:
            self._stack_combo.append_text(name)
        self._stack_combo.set_active(0)
        stack_row.append(self._stack_combo)

        add_btn = Gtk.Button(label="Add")
        add_btn.connect("clicked", self._on_add_stack)
        stack_row.append(add_btn)

        box.append(stack_row)

        hint = Gtk.Label(
            label="Presets add common terms for that stack. You can edit or add your own below."
        )
        hint.set_xalign(0)
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        hint.set_margin_bottom(4)
        box.append(hint)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(100)

        self._vocab_view = Gtk.TextView()
        self._vocab_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        scroll.set_child(self._vocab_view)
        box.append(scroll)

        vocab = self._config.get("vocabulary", [])
        if vocab:
            self._vocab_view.get_buffer().set_text("\n".join(vocab))

        return box

    def _on_add_stack(self, _btn):
        name = self._stack_combo.get_active_text()
        if not name or name not in TECH_STACKS:
            return
        terms = TECH_STACKS[name]
        buf = self._vocab_view.get_buffer()
        existing_text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        existing = {line.strip() for line in existing_text.splitlines() if line.strip()}
        new_terms = [t for t in terms if t not in existing]
        if not new_terms:
            return
        separator = "\n" if existing_text.strip() else ""
        insert_text = separator + "\n".join(new_terms)
        buf.insert(buf.get_end_iter(), insert_text)

    def _on_mic_changed(self, _combo):
        self._restart_vu_meter()

    def _restart_vu_meter(self):
        self._stop_vu_meter()
        active = self._mic_combo.get_active()
        if active >= 0 and self._mics:
            self._start_vu_meter(self._mics[active]["name"])

    def _start_vu_meter(self, source_name: str):
        self._vu_stop = threading.Event()
        threading.Thread(
            target=self._vu_worker, args=(source_name,), daemon=True
        ).start()

    def _stop_vu_meter(self):
        if hasattr(self, "_vu_stop"):
            self._vu_stop.set()
        if hasattr(self, "_vu_proc") and self._vu_proc:
            try:
                self._vu_proc.terminate()
                self._vu_proc.wait(timeout=1)
            except Exception:
                pass
            self._vu_proc = None

    def _vu_worker(self, source_name: str):
        # Use parec subprocess to avoid libpulse threading issues
        RATE = 16000
        CHANNELS = 1
        CHUNK = 800  # 50ms of s16le mono at 16kHz
        cmd = [
            "parec",
            "--raw",
            f"--channels={CHANNELS}",
            "--format=s16le",
            f"--rate={RATE}",
            "--latency-msec=50",
            "-d",
            source_name,
        ]
        self._vu_proc = None
        try:
            self._vu_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            while not self._vu_stop.is_set():
                data = self._vu_proc.stdout.read(CHUNK * 2)
                if not data:
                    break
                samples = struct.unpack(f"{len(data) // 2}h", data)
                rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0
                level = min(1.0, rms * 12)  # scale: typical speech ~0.05-0.1 RMS
                GLib.idle_add(self._update_vu, level)
        except Exception:
            pass
        finally:
            if self._vu_proc:
                try:
                    self._vu_proc.terminate()
                    self._vu_proc.wait(timeout=1)
                except Exception:
                    pass
                self._vu_proc = None

    def _update_vu(self, level: float):
        self._vu_bar.set_value(max(0.0, min(1.0, level)))
        return False

    def _enumerate_microphones(self):
        self._mic_combo.remove_all()
        self._mic_error.set_text("")
        try:
            self._mics = list_microphones()
        except pulsectl.PulseError:
            self._mic_error.set_text(
                "Could not enumerate audio devices. Is PulseAudio/PipeWire running?"
            )
            self._mics = []
            return

        current = self._config.get("microphone", "")
        for i, mic in enumerate(self._mics):
            self._mic_combo.append_text(mic["description"])
            if mic["name"] == current:
                self._mic_combo.set_active(i)

        if self._mic_combo.get_active() == -1 and self._mics:
            self._mic_combo.set_active(0)

        self._restart_vu_meter()

    def _on_validate_api_key(self, _btn):
        key = self._api_key_entry.get_text().strip()
        self._api_key_error.set_text("")
        self._spinner.start()
        self._validate_btn.set_sensitive(False)
        self._next_btn.set_sensitive(False)

        def run():
            result = validate_api_key(key)
            GLib.idle_add(self._on_validation_done, result)
            return False

        threading.Thread(target=run, daemon=True).start()

    def _on_validation_done(self, result: dict):
        self._spinner.stop()
        self._validate_btn.set_sensitive(True)
        if result["ok"]:
            self._api_key_valid = True
            self._api_key_error.set_text("")
            self._api_key_success.set_text("✓ API key valid")
            self._next_btn.set_sensitive(True)
        else:
            self._api_key_valid = False
            self._api_key_success.set_text("")
            self._api_key_error.set_text(result.get("message", "Validation failed"))
            self._next_btn.set_sensitive(False)
        return False

    def _is_skipped(self, page: str) -> bool:
        if self._provider_mode == "litellm":
            return page in ("api_key", "grok_key", "gemini_key")
        return page == "litellm"

    def _next_visible(self, index: int) -> int | None:
        for i in range(index + 1, len(self.PAGES)):
            if not self._is_skipped(self.PAGES[i]):
                return i
        return None

    def _prev_visible(self, index: int) -> int | None:
        for i in range(index - 1, -1, -1):
            if not self._is_skipped(self.PAGES[i]):
                return i
        return None

    def _update_navigation(self):
        self._back_btn.set_sensitive(self._prev_visible(self._current_page) is not None)
        is_last = self._next_visible(self._current_page) is None
        self._next_btn.set_label("Finish" if is_last else "Next")

        visible = [
            i for i in range(len(self.PAGES)) if not self._is_skipped(self.PAGES[i])
        ]
        if self._current_page in visible:
            self._progress_label.set_text(
                f"Step {visible.index(self._current_page) + 1} of {len(visible)}"
            )

        if self.PAGES[self._current_page] == "api_key":
            self._next_btn.set_sensitive(self._api_key_valid)
        else:
            self._next_btn.set_sensitive(True)

    def _on_back(self, _btn):
        prev = self._prev_visible(self._current_page)
        if prev is None:
            return
        if self.PAGES[self._current_page] == "microphone":
            self._stop_vu_meter()
        self._current_page = prev
        self._stack.set_visible_child_name(self.PAGES[prev])
        self._update_navigation()

    def _on_next(self, _btn):
        nxt = self._next_visible(self._current_page)
        if nxt is None:
            self._finish()
            return
        self._current_page = nxt
        self._stack.set_visible_child_name(self.PAGES[nxt])
        if self.PAGES[nxt] == "microphone":
            self._enumerate_microphones()
        else:
            self._stop_vu_meter()
        self._update_navigation()

    def _finish(self):
        self._stop_vu_meter()
        buf = self._vocab_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        vocab = [line.strip() for line in text.splitlines() if line.strip()]

        active = self._mic_combo.get_active()
        mic_name = self._mics[active]["name"] if self._mics and active >= 0 else ""

        config = load_config()
        config["provider_mode"] = self._provider_mode
        config["litellm_base_url"] = self._litellm_url_entry.get_text().strip()
        config["litellm_api_key"] = self._litellm_key_entry.get_text().strip()
        config["litellm_whisper_model"] = self._litellm_whisper_entry.get_text().strip()
        config["litellm_chat_model"] = self._litellm_chat_entry.get_text().strip()
        config["groq_api_key"] = self._api_key_entry.get_text().strip()
        grok_key = self._grok_key_entry.get_text().strip()
        if grok_key:
            config["grok_api_key"] = grok_key
        gemini_key = self._gemini_key_entry.get_text().strip()
        if gemini_key:
            config["gemini_api_key"] = gemini_key
        config["microphone"] = mic_name
        config["vocabulary"] = vocab
        config["setup_complete"] = True
        save_config(config)
        self.close()
