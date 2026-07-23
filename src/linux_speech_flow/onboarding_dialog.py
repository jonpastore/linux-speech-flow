import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class OnboardingDialog(Gtk.ApplicationWindow):
    def __init__(self, application, on_continue, on_quit):
        super().__init__(application=application, title="Welcome to Linux Speech Flow")
        self._on_continue = on_continue
        self._on_quit = on_quit
        self.set_default_size(480, 420)
        self.set_resizable(False)
        self.set_modal(True)
        self._build_ui()

    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(16)
        self.set_child(box)

        title = Gtk.Label(label="Linux Speech Flow")
        title.add_css_class("title-1")
        title.set_xalign(0)
        box.append(title)

        tagline = Gtk.Label(
            label="Speech-to-text for Linux. Hold a key, speak, release — text appears where you're typing."
        )
        tagline.set_xalign(0)
        tagline.set_wrap(True)
        box.append(tagline)

        priv_header = Gtk.Label()
        priv_header.set_markup("<b>Privacy</b>")
        priv_header.set_xalign(0)
        box.append(priv_header)

        privacy = Gtk.Label(
            label=(
                "Audio is processed by Groq's Whisper API. Conversation transcripts sent for "
                "AI analysis go to your chosen provider (Groq, Grok by xAI, or Google Gemini). "
                "No audio or transcription data is stored by the app beyond what you save locally. "
                "Your API keys are stored in ~/.config/linux-speech-flow/config.json "
                "(mode 0600, readable only by you)."
            )
        )
        privacy.set_xalign(0)
        privacy.set_wrap(True)
        privacy.add_css_class("dim-label")
        box.append(privacy)

        keys_header = Gtk.Label()
        keys_header.set_markup("<b>API Keys Required</b>")
        keys_header.set_xalign(0)
        box.append(keys_header)

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(4)
        box.append(grid)

        for col, text in enumerate(["Service", "Required for", "Link"]):
            lbl = Gtk.Label(label=text)
            lbl.add_css_class("heading")
            lbl.set_xalign(0)
            grid.attach(lbl, col, 0, 1, 1)

        rows = [
            ("Groq", "Required — transcription", "https://console.groq.com/"),
            ("Grok (xAI)", "Optional — conversation AI", "https://console.x.ai/"),
            (
                "Gemini",
                "Optional — conversation AI",
                "https://aistudio.google.com/apikey",
            ),
            ("Slack", "Optional — Slack integration", "https://api.slack.com/apps"),
        ]
        for row_idx, (service, req, url) in enumerate(rows, 1):
            grid.attach(Gtk.Label(label=service, xalign=0), 0, row_idx, 1, 1)
            grid.attach(Gtk.Label(label=req, xalign=0), 1, row_idx, 1, 1)
            link = Gtk.Label(xalign=0)
            link.set_markup(f'<a href="{url}">Get key</a>')
            grid.attach(link, 2, row_idx, 1, 1)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_row.append(spacer)

        quit_btn = Gtk.Button(label="Quit")
        quit_btn.connect("clicked", self._on_quit_clicked)
        btn_row.append(quit_btn)

        continue_btn = Gtk.Button(label="I understand, let's set up")
        continue_btn.add_css_class("suggested-action")
        continue_btn.connect("clicked", self._on_continue_clicked)
        btn_row.append(continue_btn)

        box.append(btn_row)

    def _on_continue_clicked(self, _btn):
        self.close()
        if self._on_continue:
            self._on_continue()

    def _on_quit_clicked(self, _btn):
        self.close()
        if self._on_quit:
            self._on_quit()
