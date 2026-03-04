import logging
import sys
import threading
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib

from pathlib import Path

from linux_speech_flow.config import load_config
from linux_speech_flow.conversation_manager import ConversationManager
from linux_speech_flow.debug_window import DebugWindow
from linux_speech_flow.history import HistoryStore, DB_PATH
from linux_speech_flow.history_window import HistoryWindow
from linux_speech_flow.notify import send_notification
from linux_speech_flow.transcription import TranscriptionPipeline, FAILED_DIR
from linux_speech_flow.tray import TrayManager, install_icons
from linux_speech_flow.wizard import WizardWindow
from linux_speech_flow.settings import SettingsWindow
from linux_speech_flow.hotkey import HotkeyManager
from linux_speech_flow.slack_manager import SlackManager
from linux_speech_flow.huddle_manager import HuddleManager
from linux_speech_flow.slack_socket import SlackSocket


class App(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.jonpastore.linux-speech-flow",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._wizard = None
        self._tray: TrayManager | None = None
        self._settings = None
        self._debug_window = None
        self._hotkey_manager = None
        self._pipeline: TranscriptionPipeline | None = None
        self._history_window: HistoryWindow | None = None
        self._history_store: HistoryStore | None = None
        self._conv_manager: ConversationManager | None = None
        self._conv_viewer = None
        self._slack_manager: SlackManager | None = None
        self._huddle_manager: HuddleManager | None = None
        self._slack_sockets: list[SlackSocket] = []
        self._huddle_dialog = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Set up logging: all linux_speech_flow.* loggers → stderr + debug window
        self._debug_window = DebugWindow(application=self)
        app_logger = logging.getLogger("linux_speech_flow")
        app_logger.setLevel(logging.DEBUG)
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S"
            )
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
            on_conversation_start=self._on_conv_start,
            on_conversation_stop=self._on_conv_stop,
            on_conversation_feedback_toggle=self._on_conv_feedback_toggle,
            on_huddle_start=self._on_huddle_start,
            on_huddle_stop=self._on_huddle_stop,
        )
        self._hotkey_manager.start()
        GLib.idle_add(self._hotkey_manager.mark_started)
        self._history_store = HistoryStore()
        self._pipeline = TranscriptionPipeline(
            on_paste_complete=self._on_paste_complete,
            on_error=self._on_pipeline_error,
            on_failed_count_changed=self._on_failed_count_changed,
            history_store=self._history_store,
            on_history_entry=self._on_history_entry_received,
        )
        self._conv_manager = ConversationManager(
            application=self,
            on_session_complete=self._on_conv_session_complete,
            on_tray_state=lambda state: self._tray.set_state(state)
            if self._tray
            else None,
        )
        self._conv_window_info: dict = {}

        self._slack_manager = SlackManager()
        self._huddle_manager = HuddleManager(
            application=self,
            slack_manager=self._slack_manager,
            on_session_complete=self._on_huddle_session_complete,
            on_tray_state=lambda state: self._tray.set_state(state)
            if self._tray
            else None,
            on_analyze=self._on_huddle_analyze,
        )
        workspaces = self._slack_manager.get_workspaces()
        for team_id, ws in workspaces.items():
            app_token = ws.get("app_token", "")
            bot_token = ws.get("bot_token", "")
            authed_user_id = ws.get("authed_user_id", "")
            if app_token and bot_token and authed_user_id:
                sock = SlackSocket()
                sock.start(
                    app_token=app_token,
                    bot_token=bot_token,
                    on_huddle_event=self._on_huddle_event_detected,
                    on_huddle_end=self._on_huddle_end_detected,
                    authed_user_id=authed_user_id,
                )
                self._slack_sockets.append(sock)

        self._tray = TrayManager(
            app=self,
            on_settings=self._on_open_settings,
            on_debug_log=self._on_open_debug_log,
            on_reprocess=self._on_reprocess_hotkey,
            on_history=self._on_open_history,
            on_conv_history=self._on_open_conv_viewer,
            on_help=self._on_open_help,
            on_huddle_toggle=self._on_huddle_toggle_tray,
        )
        self._tray.setup()

    def do_activate(self):
        config = load_config()
        if not config.get("setup_complete", False):
            if self._wizard is None:
                self._wizard = WizardWindow(application=self)
                self._wizard.connect("close-request", self._on_wizard_closed)
            self._wizard.present()
        else:
            self.hold()

    def _on_wizard_closed(self, _window):
        self._wizard = None

    def _on_open_settings(self, _btn=None):
        if self._settings is None:
            self._settings = SettingsWindow(
                application=self, hotkey_manager=self._hotkey_manager
            )
            self._settings.connect("close-request", self._on_settings_closed)
        self._settings.present()

    def _on_settings_closed(self, _window):
        self._settings = None
        if self._hotkey_manager:
            self._hotkey_manager.reload_bindings()
        return False

    def _on_open_history(self, _btn=None):
        if self._history_window is None:
            self._history_window = HistoryWindow(
                application=self,
                history_store=self._history_store,
            )
            self._history_window.connect("close-request", self._on_history_closed)
        self._history_window.present()

    def _on_history_closed(self, _window):
        self._history_window = None
        return False

    def _on_history_entry_received(self, entry: dict) -> bool:
        if self._history_window is not None:
            self._history_window.prepend_entry(entry)
        return False

    def _on_open_debug_log(self, _btn=None):
        self._debug_window.present()

    def _on_open_help(self, _btn=None):
        from linux_speech_flow.help_window import HelpWindow

        if not hasattr(self, "_help_window") or not self._help_window:
            self._help_window = HelpWindow(application=self)
            self._help_window.connect(
                "close-request", lambda _w: setattr(self, "_help_window", None)
            )
        self._help_window.present()

    def _on_recording_start(self) -> None:
        if self._tray:
            self._tray.set_state("recording")

    def _on_recording_complete(
        self, wav_path: str, stop_was_hotkey: bool = False
    ) -> None:
        if self._tray:
            self._tray.set_state("processing")
        if self._pipeline is None:
            return
        depth = self._pipeline.submit(wav_path, stop_was_hotkey=stop_was_hotkey)
        if depth > 1:
            send_notification("Recording queued", f"{depth} pending")

    def _on_recording_error(self, message: str) -> None:
        if self._tray:
            self._tray.set_state("error")
        send_notification("Linux Speech Flow Error", message)

    def _on_paste_complete(self) -> bool:
        if self._tray:
            self._tray.set_state("idle")
        return False

    def _on_pipeline_error(self, message: str) -> None:
        if self._tray:
            self._tray.set_state("error")
        send_notification("Linux Speech Flow Error", message)

    def _on_failed_count_changed(self, count: int) -> bool:
        if self._tray:
            self._tray.update_failed_count(count)
        return False

    def _install_autostart(self) -> None:
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        old_desktop = autostart_dir / "freeflow.desktop"
        old_desktop.unlink(missing_ok=True)
        desktop_path = autostart_dir / "linux-speech-flow.desktop"
        venv_python = sys.executable
        content = (
            "[Desktop Entry]\n"
            "Name=Linux Speech Flow\n"
            "Comment=Linux speech-to-text assistant\n"
            f"Exec={venv_python} -m linux_speech_flow\n"
            "Icon=linux-speech-flow-idle\n"
            "Type=Application\n"
            "StartupNotify=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        desktop_path.write_text(content)
        logger.info("autostart installed: %s", desktop_path)

    def _on_reprocess_hotkey(self) -> None:
        """Called from HotkeyManager when Ctrl+Alt+P is pressed."""
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

    def _on_conv_start(self) -> None:
        from linux_speech_flow.window_context import get_active_window_info

        self._conv_window_info = get_active_window_info(
            app_categories=load_config().get("app_categories", {})
        )
        if self._conv_manager:
            self._conv_manager.start_session()

    def _on_conv_stop(self) -> None:
        if self._conv_manager:
            self._conv_manager.stop_session(reason="user_hotkey")

    def _on_conv_feedback_toggle(self) -> None:
        if self._conv_manager:
            self._conv_manager.toggle_feedback()

    def _on_huddle_event_detected(self, event: dict) -> None:
        """Called on GTK main thread via GLib.idle_add when SlackSocket detects a huddle start.

        Dispatches based on slack_huddle_auto_detect config:
          'always' — start recording immediately
          'prompt' — show tray notification with Start Recording action
          'manual' — ignore (user uses Ctrl+Alt+H or tray item only)
        """
        config = load_config()
        auto_detect = config.get("slack_huddle_auto_detect", "prompt")
        if auto_detect == "manual":
            return
        huddle_state = event.get("huddle_state") or {}
        channel_id = huddle_state.get("channel_id") or huddle_state.get("call", {}).get(
            "channel_id", ""
        )
        team_id = event.get("team_id", "")
        if not channel_id and team_id:
            channel_id = (
                config.get("slack_workspaces", {})
                .get(team_id, {})
                .get("channel_id", "")
            )
            if channel_id:
                logger.warning(
                    "channel_id not found in huddle event; using configured channel_id '%s' for team %s",
                    channel_id,
                    team_id,
                )
        if auto_detect == "always":
            self._on_huddle_start_for(team_id, channel_id)
        else:
            send_notification(
                "Huddle detected",
                body="Slack huddle started. Press Ctrl+Alt+H or use the tray to start recording.",
            )

    def _on_huddle_end_detected(self) -> None:
        """Called on GTK main thread via GLib.idle_add when SlackSocket detects huddle ended.

        Stops the active HuddleManager session (SLACK-05 auto-stop requirement).
        No-op if no session is currently active.
        """
        if self._huddle_manager and self._huddle_manager.is_active():
            logger.info("Huddle ended (auto-detected); stopping session")
            self._on_huddle_stop()

    def _on_huddle_start_for(self, team_id: str, channel_id: str) -> None:
        """Start a huddle session for a specific team/channel (used by auto-detect)."""
        if self._huddle_manager:
            self._huddle_manager.start_session(team_id=team_id, channel_id=channel_id)
            if self._tray:
                self._tray.set_huddle_recording(True)

    def _on_huddle_start(self) -> None:
        """Called by HotkeyManager when Ctrl+Alt+H is pressed in idle state."""
        if self._huddle_manager:
            config = load_config()
            workspaces = config.get("slack_workspaces", {})
            if not workspaces:
                send_notification(
                    "No Slack workspace connected",
                    body="Add a workspace in Settings → Integrations",
                )
                if self._hotkey_manager:
                    self._hotkey_manager.reset_to_idle()
                return
            team_id = next(iter(workspaces))
            channel_id = workspaces[team_id].get("channel_id", "")
            self._on_huddle_start_for(team_id, channel_id)

    def _on_huddle_stop(self) -> None:
        if self._huddle_manager:
            self._huddle_manager.stop_session()
            if self._tray:
                self._tray.set_huddle_recording(False)

    def _on_huddle_toggle_tray(self) -> None:
        """Toggle huddle recording via tray menu item.

        Calls public _on_huddle_start/_on_huddle_stop callbacks directly
        rather than accessing private HotkeyManager state. HotkeyManager's
        _huddle_start/_stop already guard against invalid state transitions.
        """
        if self._huddle_manager:
            if not self._huddle_manager.is_active():
                self._on_huddle_start()
            else:
                self._on_huddle_stop()

    def _on_huddle_dialog_closed(self, _win) -> bool:
        self._huddle_dialog = None
        return False

    def _on_huddle_session_complete(self, transcript: str, metadata: dict) -> None:
        """Reuse ConversationPipeline post-stop dialog; after Q&A, post to Slack."""
        from linux_speech_flow.conversation_dialog import ConversationDialog

        if self._huddle_dialog is not None:
            logger.warning("_on_huddle_session_complete: dialog already open — closing it first")
            self._huddle_dialog.close()

        if self._huddle_manager:
            self._huddle_manager.debug_post("analysis dialog presented to user", "medium")

        dialog = ConversationDialog(
            application=self,
            transcript=transcript,
            metadata=metadata,
            on_submit=lambda *args, **kwargs: self._on_huddle_dialog_submit(
                *args, huddle_metadata=metadata, **kwargs
            ),
        )
        self._huddle_dialog = dialog
        dialog.connect("close-request", self._on_huddle_dialog_closed)
        dialog.present()

    def _on_huddle_analyze(self, transcript: str, metadata: dict) -> None:
        """Called by HuddleManager.trigger_analyze() when Analyze button clicked mid-session.

        Shows ConversationDialog with current transcript snapshot. On any close
        (submit or cancel), calls resume_from_analyze() so recording resumes.
        """
        from linux_speech_flow.conversation_dialog import ConversationDialog

        if self._huddle_dialog is not None:
            logger.warning("_on_huddle_analyze: dialog already open — ignoring duplicate")
            return

        def _on_resume():
            if self._huddle_manager:
                self._huddle_manager.resume_from_analyze()

        dialog = ConversationDialog(
            application=self,
            transcript=transcript,
            metadata=metadata,
            on_submit=lambda *args, **kwargs: self._on_huddle_dialog_submit(
                *args, huddle_metadata=metadata, **kwargs
            ),
            on_cancel=_on_resume,
        )
        self._huddle_dialog = dialog
        dialog.connect("close-request", self._on_huddle_dialog_closed)
        dialog.present()

    def _on_huddle_dialog_submit(
        self,
        transcript,
        prompt,
        qualifying_answers,
        selected_models,
        save_to_file,
        inject_to_window,
        metadata,
        copy_to_clipboard=False,
        paste_to_window=False,
        window_info=None,
        huddle_metadata=None,
    ):
        from pathlib import Path
        from linux_speech_flow.conversation_pipeline import conv_filename, coalesce_file

        config = load_config()
        save_dir = Path(
            config.get("conv_save_dir", "~/Documents/conversations")
        ).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)

        initial_path = str(save_dir / conv_filename("huddle"))
        if save_to_file:
            coalesce_file(initial_path, metadata, "", [], transcript)

        def on_finalised(final_path: str) -> None:
            if huddle_metadata and self._huddle_manager:
                team_id = huddle_metadata.get("team_id")
                channel_id = huddle_metadata.get("channel_id")
                if team_id and channel_id:
                    threading.Thread(
                        target=self._huddle_manager.post_huddle_results,
                        args=(team_id, channel_id, {}, final_path),
                        daemon=True,
                    ).start()

        if not selected_models:
            if self._huddle_manager:
                self._huddle_manager.debug_post("analysis skipped — no models selected", "medium")
            if save_to_file:
                on_finalised(initial_path)
            return

        if self._huddle_manager:
            self._huddle_manager.debug_post(
                f"analysis submitted — models: {', '.join(selected_models)}", "medium"
            )
        pipeline = self._conv_manager._pipeline if self._conv_manager else None
        if pipeline is None:
            from linux_speech_flow.conversation_pipeline import ConversationPipeline

            pipeline = ConversationPipeline()

        def _analyze_thread():
            result = pipeline.analyze(
                transcript, prompt, qualifying_answers, selected_models
            )
            GLib.idle_add(_open_qa, result)

        def _open_qa(result):
            from linux_speech_flow.conversation_qa import ConversationQAWindow

            qa_window = ConversationQAWindow(
                application=self,
                transcript=transcript,
                metadata=metadata,
                pipeline=pipeline,
                initial_result=result,
                save_path=initial_path,
                on_finalised=lambda final_path: self._on_huddle_analysis_complete(
                    result, final_path, huddle_metadata
                ),
                selected_models=selected_models,
            )
            qa_window.present()
            return False

        threading.Thread(target=_analyze_thread, daemon=True).start()

    def _on_huddle_analysis_complete(
        self, result: dict, saved_path: str | None, metadata: dict
    ) -> None:
        """After post-huddle Q&A completes: show channel picker, then post to Slack."""
        team_id = metadata.get("team_id") if metadata else None
        default_channel_id = metadata.get("channel_id") if metadata else None
        if not team_id or not self._huddle_manager:
            return

        win = Gtk.Window(title="Post to Slack")
        win.set_modal(True)
        win.set_default_size(380, 180)
        win.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        win.set_child(box)

        label = Gtk.Label(label="Select channel to post results:")
        label.set_xalign(0)
        box.append(label)

        combo = Gtk.ComboBoxText()
        combo.set_sensitive(False)
        combo.append_text("Loading channels...")
        combo.set_active(0)
        box.append(combo)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_row.append(spacer)
        box.append(btn_row)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: win.close())
        btn_row.append(cancel_btn)

        post_btn = Gtk.Button(label="Post to Slack")
        post_btn.add_css_class("suggested-action")
        post_btn.set_sensitive(False)
        btn_row.append(post_btn)

        _channel_list: list[tuple[str, str]] = []

        def _populate_channels():
            channels = self._slack_manager.get_channels(team_id)
            GLib.idle_add(_apply_channels, channels)

        def _apply_channels(channels: list[tuple[str, str]]) -> bool:
            nonlocal _channel_list
            _channel_list = channels
            combo.remove_all()
            default_idx = 0
            for i, (ch_id, ch_name) in enumerate(channels):
                combo.append_text(f"#{ch_name}")
                if ch_id == default_channel_id:
                    default_idx = i
            if channels:
                combo.set_active(default_idx)
                combo.set_sensitive(True)
                post_btn.set_sensitive(True)
            else:
                combo.append_text("(no channels found)")
                combo.set_active(0)
            return False

        threading.Thread(target=_populate_channels, daemon=True).start()

        def _on_post(_btn):
            idx = combo.get_active()
            if idx < 0 or idx >= len(_channel_list):
                return
            selected_channel_id = _channel_list[idx][0]
            win.close()
            threading.Thread(
                target=self._huddle_manager.post_huddle_results,
                args=(team_id, selected_channel_id, result or {}, saved_path),
                daemon=True,
            ).start()

        post_btn.connect("clicked", _on_post)
        win.present()

    def _on_conv_session_complete(self, transcript: str, metadata: dict) -> bool:
        """Called on GTK main thread by ConversationManager when session ends."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            "conv_session_complete: transcript=%d chars window_id=%s wm_class=%r",
            len(transcript),
            self._conv_window_info.get("window_id"),
            self._conv_window_info.get("wm_class"),
        )
        from linux_speech_flow.conversation_dialog import ConversationDialog

        dialog = ConversationDialog(
            application=self,
            transcript=transcript,
            metadata=metadata,
            on_submit=self._on_conv_dialog_submit,
            window_info=self._conv_window_info,
        )
        dialog.present()
        return False

    def _on_conv_dialog_submit(
        self,
        transcript,
        prompt,
        qualifying_answers,
        selected_models,
        save_to_file,
        inject_to_window,
        metadata,
        copy_to_clipboard=False,
        paste_to_window=False,
        window_info=None,
    ):
        import logging
        from pathlib import Path
        from linux_speech_flow.conversation_pipeline import conv_filename, coalesce_file
        from linux_speech_flow.conversation_qa import ConversationQAWindow

        logger = logging.getLogger(__name__)
        config = load_config()

        # Immediate raw transcript actions (before AI analysis)
        if copy_to_clipboard:
            from linux_speech_flow.injector import copy_to_clipboard as _copy

            logger.info(
                "conv_dialog_submit: copying transcript to clipboard (%d chars)",
                len(transcript),
            )
            _copy(transcript)

        if paste_to_window and window_info and window_info.get("window_id"):
            from linux_speech_flow.injector import paste_text

            logger.info(
                "conv_dialog_submit: pasting transcript to window_id=%s",
                window_info.get("window_id"),
            )
            paste_text(transcript, window_info)
        save_dir = Path(
            config.get("conv_save_dir", "~/Documents/conversations")
        ).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)

        initial_path = str(save_dir / conv_filename("untitled"))
        if save_to_file:
            coalesce_file(initial_path, metadata, "", [], transcript)

        def on_finalised(final_path: str) -> None:
            if inject_to_window and window_info and window_info.get("window_id"):
                try:
                    content = Path(final_path).read_text(encoding="utf-8")
                    from linux_speech_flow.injector import paste_text

                    logger.info(
                        "conv_on_finalised: injecting analysis to window_id=%s",
                        window_info.get("window_id"),
                    )
                    paste_text(content, window_info)
                except Exception as exc:
                    logger.error("conv_on_finalised: inject failed: %s", exc)

        if not selected_models:
            if save_to_file:
                on_finalised(initial_path)
            return

        pipeline = self._conv_manager._pipeline if self._conv_manager else None
        if pipeline is None:
            from linux_speech_flow.conversation_pipeline import ConversationPipeline

            pipeline = ConversationPipeline()

        def _analyze_thread():
            result = pipeline.analyze(
                transcript, prompt, qualifying_answers, selected_models
            )
            GLib.idle_add(_open_qa, result)

        def _open_qa(result):
            qa_window = ConversationQAWindow(
                application=self,
                transcript=transcript,
                metadata=metadata,
                pipeline=pipeline,
                initial_result=result,
                save_path=initial_path,
                on_finalised=on_finalised,
                selected_models=selected_models,
            )
            qa_window.present()
            return False

        threading.Thread(target=_analyze_thread, daemon=True).start()

    def _on_open_conv_viewer(self, _btn=None):
        if self._conv_viewer is None:
            from linux_speech_flow.conversation_viewer import ConversationViewer

            self._conv_viewer = ConversationViewer(
                application=self,
                on_continue_qa=self._on_conv_continue_qa,
            )
            self._conv_viewer.connect("close-request", self._on_conv_viewer_closed)
        self._conv_viewer.present()

    def _on_conv_viewer_closed(self, _window):
        self._conv_viewer = None
        return False

    def _on_conv_continue_qa(self, file_path: str) -> None:
        """Re-open Q&A for an existing conversation file. Reads transcript from file."""
        from pathlib import Path

        try:
            content = Path(file_path).read_text(encoding="utf-8")
            if "## Transcript" in content:
                transcript = content.split("## Transcript", 1)[1].strip()
            else:
                transcript = content
        except OSError:
            return
        metadata = {}
        for line in content.splitlines()[:6]:
            if ":" in line and not line.startswith("#"):
                k, v = line.split(":", 1)
                metadata[k.strip().lower().replace(" ", "_")] = v.strip()
        self._on_conv_dialog_submit(
            transcript, "", "", ["groq"], False, False, metadata
        )

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
        if (
            self._conv_manager
            and hasattr(self._conv_manager, "_recorder")
            and self._conv_manager._recorder
        ):
            self._conv_manager._recorder.stop()
        if self._huddle_manager and self._huddle_manager.is_active():
            self._huddle_manager.stop_session()
        Gtk.Application.do_shutdown(self)


logger = logging.getLogger(__name__)


def main():
    app = App()
    return app.run(sys.argv)
