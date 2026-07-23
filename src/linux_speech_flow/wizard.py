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
        "api_key",
        "grok_key",
        "gemini_key",
        "slack_key",
        "microphone",
        "vocabulary",
    ]

    def __init__(self, application, config: dict | None = None):
        super().__init__(application=application, title="linux-speech-flow Setup")
        self._config = config if config is not None else load_config()
        self._api_key_valid = False
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

        self._stack.add_named(self._build_api_key_page(), "api_key")
        self._stack.add_named(self._build_grok_key_page(), "grok_key")
        self._stack.add_named(self._build_gemini_key_page(), "gemini_key")
        self._stack.add_named(self._build_slack_key_page(), "slack_key")
        self._stack.add_named(self._build_microphone_page(), "microphone")
        self._stack.add_named(self._build_vocabulary_page(), "vocabulary")

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

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        nav.append(spacer)

        self._next_btn = Gtk.Button(label="Next")
        self._next_btn.connect("clicked", self._on_next)
        self._next_btn.add_css_class("suggested-action")
        nav.append(self._next_btn)

        self._update_navigation()

    def _build_api_key_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(12)

        title = Gtk.Label(label="Step 1 of 6: Groq API Key")
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

        title = Gtk.Label(label="Step 2 of 6: Grok API Key (optional)")
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

        title = Gtk.Label(label="Step 3 of 6: Gemini API Key (optional)")
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

        title = Gtk.Label(label="Step 4 of 6: Slack Integration (optional)")
        title.add_css_class("title-2")
        title.set_xalign(0)
        box.append(title)

        desc = Gtk.Label(
            label=(
                "Slack integration lets linux-speech-flow post transcriptions to Slack "
                "and record Slack huddle sessions.\n\n"
                "Slack requires creating a Slack App with specific permissions — see the README "
                "for the full setup guide. You can connect Slack at any time via Settings > Integrations."
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

        title = Gtk.Label(label="Step 5 of 6: Microphone")
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

        title = Gtk.Label(label="Step 6 of 6: Vocabulary (optional)")
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

    def _update_navigation(self):
        self._back_btn.set_sensitive(self._current_page > 0)
        is_last = self._current_page == len(self.PAGES) - 1
        self._next_btn.set_label("Finish" if is_last else "Next")

        if self._current_page == 0:
            self._next_btn.set_sensitive(self._api_key_valid)
        else:
            self._next_btn.set_sensitive(True)

    def _on_back(self, _btn):
        if self._current_page > 0:
            if self.PAGES[self._current_page] == "microphone":
                self._stop_vu_meter()
            self._current_page -= 1
            self._stack.set_visible_child_name(self.PAGES[self._current_page])
            self._update_navigation()

    def _on_next(self, _btn):
        if self._current_page < len(self.PAGES) - 1:
            self._current_page += 1
            self._stack.set_visible_child_name(self.PAGES[self._current_page])
            if self.PAGES[self._current_page] == "microphone":
                self._enumerate_microphones()
            else:
                self._stop_vu_meter()
            self._update_navigation()
        else:
            self._finish()

    def _finish(self):
        self._stop_vu_meter()
        buf = self._vocab_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        vocab = [line.strip() for line in text.splitlines() if line.strip()]

        active = self._mic_combo.get_active()
        mic_name = self._mics[active]["name"] if self._mics and active >= 0 else ""

        config = load_config()
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
