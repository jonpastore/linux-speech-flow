import logging
import sys
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib

from pathlib import Path

from linux_speech_flow.config import load_config
from linux_speech_flow.debug_window import DebugWindow
from linux_speech_flow.notify import send_notification
from linux_speech_flow.transcription import TranscriptionPipeline, FAILED_DIR
from linux_speech_flow.tray import TrayManager, install_icons
from linux_speech_flow.wizard import WizardWindow
from linux_speech_flow.settings import SettingsWindow
from linux_speech_flow.hotkey import HotkeyManager


class App(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.linux-speech-flow",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._wizard = None
        self._tray: TrayManager | None = None
        self._settings = None
        self._debug_window = None
        self._hotkey_manager = None
        self._pipeline: TranscriptionPipeline | None = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Set up logging: all linux_speech_flow.* loggers → stderr + debug window
        self._debug_window = DebugWindow(application=self)
        app_logger = logging.getLogger("linux_speech_flow")
        app_logger.setLevel(logging.DEBUG)
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")
        )
        app_logger.addHandler(stderr_handler)
        app_logger.addHandler(self._debug_window.as_log_handler())
        app_logger.propagate = False

        install_icons()
        self._install_autostart()

        self._hotkey_manager = HotkeyManager(
            on_recording_start=self._on_recording_start,
            on_recording_complete=self._on_recording_complete,
            on_recording_error=self._on_recording_error,
            on_reprocess=self._on_reprocess_hotkey,
        )
        self._hotkey_manager.start()
        GLib.idle_add(self._hotkey_manager.mark_started)
        self._pipeline = TranscriptionPipeline(
            on_paste_complete=self._on_paste_complete,
            on_error=self._on_pipeline_error,
            on_failed_count_changed=self._on_failed_count_changed,
        )

        self._tray = TrayManager(
            app=self,
            on_settings=self._on_open_settings,
            on_debug_log=self._on_open_debug_log,
            on_reprocess=self._on_reprocess_hotkey,
        )
        self._tray.setup()

    def do_activate(self):
        config = load_config()
        if not config.get('setup_complete', False):
            if self._wizard is None:
                self._wizard = WizardWindow(application=self)
                self._wizard.connect('close-request', self._on_wizard_closed)
            self._wizard.present()
        else:
            self.hold()

    def _on_wizard_closed(self, _window):
        self._wizard = None

    def _on_open_settings(self, _btn=None):
        if self._settings is None:
            self._settings = SettingsWindow(application=self)
            self._settings.connect("close-request", self._on_settings_closed)
        self._settings.present()

    def _on_settings_closed(self, _window):
        self._settings = None
        return False

    def _on_open_debug_log(self, _btn=None):
        self._debug_window.present()

    def _on_recording_start(self) -> None:
        if self._tray:
            self._tray.set_state('recording')

    def _on_recording_complete(self, wav_path: str, stop_was_f9: bool = False) -> None:
        if self._tray:
            self._tray.set_state('processing')
        if self._pipeline is None:
            return
        depth = self._pipeline.submit(wav_path, stop_was_f9=stop_was_f9)
        if depth > 1:
            send_notification('Recording queued', f'{depth} pending')

    def _on_recording_error(self, message: str) -> None:
        if self._tray:
            self._tray.set_state('error')
        send_notification('Linux Speech Flow Error', message)

    def _on_paste_complete(self) -> bool:
        if self._tray:
            self._tray.set_state('idle')
        return False

    def _on_pipeline_error(self, message: str) -> None:
        if self._tray:
            self._tray.set_state('error')
        send_notification('Linux Speech Flow Error', message)

    def _on_failed_count_changed(self, count: int) -> bool:
        if self._tray:
            self._tray.update_failed_count(count)
        return False

    def _install_autostart(self) -> None:
        autostart_dir = Path.home() / '.config' / 'autostart'
        autostart_dir.mkdir(parents=True, exist_ok=True)
        old_desktop = autostart_dir / 'freeflow.desktop'
        old_desktop.unlink(missing_ok=True)
        desktop_path = autostart_dir / 'linux-speech-flow.desktop'
        venv_python = sys.executable
        content = (
            '[Desktop Entry]\n'
            'Name=Linux Speech Flow\n'
            'Comment=Linux speech-to-text assistant\n'
            f'Exec={venv_python} -m linux_speech_flow\n'
            'Icon=linux-speech-flow-idle\n'
            'Type=Application\n'
            'StartupNotify=false\n'
            'X-GNOME-Autostart-enabled=true\n'
        )
        desktop_path.write_text(content)
        logger.info('autostart installed: %s', desktop_path)

    def _on_reprocess_hotkey(self) -> None:
        """Called from HotkeyManager when F10 is pressed."""
        from linux_speech_flow.reprocess_dialog import ReprocessDialog
        if not FAILED_DIR.exists():
            return
        failed_wavs = sorted(FAILED_DIR.glob("*.wav"))
        if not failed_wavs:
            send_notification("No failed recordings", "Nothing to reprocess.")
            return
        if len(failed_wavs) == 1:
            self._pipeline.submit(str(failed_wavs[0]))
        else:
            dialog = ReprocessDialog(
                failed_wavs=[str(p) for p in failed_wavs],
                on_selected=self._on_reprocess_selected,
                application=self,
            )
            dialog.present()

    def _on_reprocess_selected(self, wav_paths: list[str], mode: str) -> None:
        """Callback from ReprocessDialog with selected paths and mode.

        mode: "paste" — submit each WAV to pipeline sequentially (FIFO)
              "file"  — write all transcripts to a temp file and open it
        """
        if mode == "paste":
            for path in wav_paths:
                self._pipeline.submit(path)
        elif mode == "file":
            self._pipeline.submit_batch_to_file(wav_paths)

    def do_shutdown(self):
        if self._hotkey_manager:
            self._hotkey_manager.stop()
        Gtk.Application.do_shutdown(self)


logger = logging.getLogger(__name__)


def main():
    app = App()
    return app.run(sys.argv)
