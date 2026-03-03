import logging
import os
import threading
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from linux_speech_flow.config import load_config
from linux_speech_flow.conversation_recorder import ConversationRecorder
from linux_speech_flow.conversation_pipeline import ConversationPipeline
from linux_speech_flow.sounds import play_sound

logger = logging.getLogger(__name__)

_STATE_IDLE = "idle"
_STATE_CONVERSATION = "conversation"


class ConversationManager:
    """Owns the conversation recording session lifecycle.

    Threading contract:
    - start_session() / stop_session() / toggle_feedback() called on GTK main thread.
    - on_chunk_ready dispatched via GLib.idle_add (GTK main thread).
    - Per-chunk Whisper transcription runs in daemon threads.
    - All GLib timer callbacks run on GTK main thread.
    - on_session_complete callback fires on GTK main thread.
    """

    def __init__(self, application, on_session_complete, on_tray_state):
        """
        Args:
            application: Gtk.Application (for window creation)
            on_session_complete: Callable(transcript: str, metadata: dict) --
                called on GTK main thread when session ends normally.
                metadata has keys: date, duration, chunk_count, models_used.
            on_tray_state: Callable(state: str) -- called to update tray icon.
        """
        self._app = application
        self._on_session_complete = on_session_complete
        self._on_tray_state = on_tray_state
        self._state = _STATE_IDLE
        self._recorder: ConversationRecorder | None = None
        self._pipeline = ConversationPipeline()
        self._status_window = None
        self._chunk_texts: list[str] = []
        self._chunk_count = 0
        self._session_start: float | None = None

        # Session-level silence timer IDs
        self._warn_timer: int | None = None
        self._stop_timer: int | None = None
        self._hard_limit_timer: int | None = None

        # Silence display accumulation (across chunk boundaries)
        self._silence_offset_sec: int = 0
        self._last_silence_frames: int = 0

    def start_session(self) -> None:
        """Start a new conversation recording session. Called on GTK main thread."""
        if self._state != _STATE_IDLE:
            return
        self._state = _STATE_CONVERSATION
        self._chunk_texts = []
        self._chunk_count = 0
        self._session_start = time.monotonic()
        self._silence_offset_sec = 0
        self._last_silence_frames = 0
        if self._on_tray_state:
            self._on_tray_state('conv_recording')

        config = load_config()
        play_sound("start.wav",
                   output_device=config.get("sounds_output_device", ""),
                   enabled=config.get("sounds_enabled", True))

        feedback_mode = config.get("conv_feedback_mode", "status_window")
        if feedback_mode == "status_window":
            self._show_status_window()

        device_name = config.get("microphone", "")
        chunk_silence_sec = config.get("conv_chunk_silence_sec", 3)
        self._recorder = ConversationRecorder(
            device_name=device_name,
            chunk_silence_sec=chunk_silence_sec,
        )
        self._recorder.start(
            on_chunk_ready=self._on_chunk_ready,
            on_error=self._on_recorder_error,
            on_silence_tick=self._on_silence_tick,
        )

        # Hard limit timer
        hard_limit = config.get("conv_hard_limit_sec", 14400)
        self._hard_limit_timer = GLib.timeout_add_seconds(
            hard_limit, self._on_hard_limit
        )
        # Start session silence detection timer immediately
        self._reset_silence_timers()

    def stop_session(self) -> None:
        """Stop recording and assemble final transcript. Called on GTK main thread."""
        if self._state != _STATE_CONVERSATION:
            return
        self._state = _STATE_IDLE
        self._cancel_all_timers()

        if self._recorder:
            self._recorder.stop()
            # Note: recorder fires on_chunk_ready for the last chunk via GLib.idle_add
            # We give it a moment to fire before assembling transcript.
            # Use GLib.timeout_add to defer assembly until pending idle callbacks run.
            GLib.timeout_add(500, self._finish_session)
        else:
            self._finish_session()

    def toggle_feedback(self) -> None:
        """Fn+D handler: toggle between tray-only and status window. GTK main thread."""
        config = load_config()
        current = config.get("conv_feedback_mode", "status_window")
        if current == "status_window":
            if self._status_window:
                self._status_window.stop()
                self._status_window.close()
                self._status_window = None
            config["conv_feedback_mode"] = "tray_only"
        else:
            config["conv_feedback_mode"] = "status_window"
            if self._state == _STATE_CONVERSATION:
                self._show_status_window()
        from linux_speech_flow.config import save_config
        save_config(config)

    # --- Internal GTK-thread methods ---

    def _show_status_window(self) -> None:
        from linux_speech_flow.conversation_status import ConversationStatusWindow
        if self._status_window is None:
            self._status_window = ConversationStatusWindow(application=self._app)
        self._status_window.start()
        self._status_window.present()

    def _on_chunk_ready(self, wav_path: str) -> bool:
        """Called on GTK main thread when recorder delivers a chunk."""
        if self._state != _STATE_CONVERSATION:
            return False
        self._reset_silence_timers()
        self._chunk_count += 1
        logger.info("Conversation chunk %d ready: %s", self._chunk_count, wav_path)
        if self._status_window:
            self._status_window.update_status(self._chunk_count, "transcribing...")
        threading.Thread(
            target=self._transcribe_chunk_thread,
            args=(wav_path, self._chunk_count),
            daemon=True,
        ).start()
        return False

    def _transcribe_chunk_thread(self, wav_path: str, chunk_num: int) -> None:
        """Worker thread: transcribe one chunk, then clean up WAV."""
        try:
            text = self._pipeline.transcribe_chunk(wav_path)
            GLib.idle_add(self._on_chunk_transcribed, text, chunk_num)
        except Exception as exc:
            logger.error("Chunk %d transcription failed: %s", chunk_num, exc)
            GLib.idle_add(self._on_chunk_transcribed, "", chunk_num)
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    def _on_chunk_transcribed(self, text: str, chunk_num: int) -> bool:
        """GTK main thread: store transcribed text."""
        if text:
            self._chunk_texts.append(text)
        if self._status_window:
            ts_ago = "just now"
            self._status_window.update_status(
                len(self._chunk_texts),
                f"last chunk: {ts_ago}"
            )
            if text:
                self._status_window.update_transcript(text)
        return False

    def _on_recorder_error(self, message: str) -> bool:
        """GTK main thread: recorder mic error."""
        logger.error("Conversation recorder error: %s", message)
        self.stop_session()
        return False

    def _on_silence_tick(self, silence_frames: int) -> bool:
        """GTK main thread (via GLib.idle_add): forward silence counter to status window.

        silence_frames is the per-chunk frame count. When a new chunk starts after a
        silence boundary, frames reset to 0. We carry forward the prior silence via
        _silence_offset_sec so the display counts up continuously across chunk boundaries.
        """
        if silence_frames == 0:
            # Voice detected — reset accumulated silence
            self._silence_offset_sec = 0
        elif self._last_silence_frames > silence_frames:
            # frames went backwards (new chunk started after silence boundary)
            self._silence_offset_sec += int(self._last_silence_frames * 0.1)
        self._last_silence_frames = silence_frames
        if self._status_window:
            silence_sec = self._silence_offset_sec + int(silence_frames * 0.1)
            self._status_window.update_silence(silence_sec)
        return False

    def _reset_silence_timers(self) -> None:
        """Cancel existing session silence timers and start fresh."""
        if self._warn_timer:
            GLib.source_remove(self._warn_timer)
            self._warn_timer = None
        if self._stop_timer:
            GLib.source_remove(self._stop_timer)
            self._stop_timer = None
        config = load_config()
        warn_sec = config.get("conv_silence_warn_sec", 180)
        self._warn_timer = GLib.timeout_add_seconds(warn_sec, self._on_silence_warn)

    def _on_silence_warn(self) -> bool:
        """180s silence: show GTK modal prompting Continue or Stop."""
        self._warn_timer = None
        self._show_silence_modal()
        config = load_config()
        stop_sec = config.get("conv_silence_stop_sec", 300)
        warn_sec = config.get("conv_silence_warn_sec", 180)
        extra = max(stop_sec - warn_sec, 30)
        self._stop_timer = GLib.timeout_add_seconds(extra, self._on_silence_autostop)
        return False

    def _show_silence_modal(self) -> None:
        elapsed = int(time.monotonic() - self._session_start) if self._session_start else 0
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        elapsed_str = f"{h}:{m:02d}:{s:02d}"

        dialog = Gtk.Window(title="Still recording?")
        dialog.set_modal(True)
        dialog.set_transient_for(self._status_window)
        dialog.set_default_size(400, 180)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        dialog.set_child(box)

        msg = Gtk.Label()
        msg.set_markup(
            f"<b>No speech detected for a while.</b>\n"
            f"Elapsed: {elapsed_str} | {len(self._chunk_texts)} chunk(s) transcribed\n"
            "Do you want to continue or stop the recording?"
        )
        msg.set_wrap(True)
        box.append(msg)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        box.append(btn_box)

        stop_btn = Gtk.Button(label="Stop Recording")
        stop_btn.connect("clicked", lambda _b: (dialog.close(), self.stop_session()))
        btn_box.append(stop_btn)

        continue_btn = Gtk.Button(label="Continue")
        continue_btn.add_css_class("suggested-action")
        continue_btn.connect("clicked", lambda _b: (dialog.close(), self._reset_silence_timers()))
        btn_box.append(continue_btn)

        dialog.present()

    def _on_silence_autostop(self) -> bool:
        """300s total silence: auto-stop with audio cue."""
        self._stop_timer = None
        config = load_config()
        play_sound("stop.wav",
                   output_device=config.get("sounds_output_device", ""),
                   enabled=config.get("sounds_enabled", True))
        self.stop_session()
        return False

    def _on_hard_limit(self) -> bool:
        """4hr hard limit: play warning sound and stop."""
        self._hard_limit_timer = None
        config = load_config()
        play_sound("error.wav",
                   output_device=config.get("sounds_output_device", ""),
                   enabled=config.get("sounds_enabled", True))
        self.stop_session()
        return False

    def _cancel_all_timers(self) -> None:
        for attr in ('_warn_timer', '_stop_timer', '_hard_limit_timer'):
            tid = getattr(self, attr)
            if tid:
                GLib.source_remove(tid)
                setattr(self, attr, None)

    def _finish_session(self) -> bool:
        """Assemble final transcript and fire on_session_complete. GTK main thread."""
        config = load_config()
        play_sound("stop.wav",
                   output_device=config.get("sounds_output_device", ""),
                   enabled=config.get("sounds_enabled", True))

        if self._status_window:
            self._status_window.stop()
            self._status_window.close()
            self._status_window = None
        if self._on_tray_state:
            self._on_tray_state('idle')

        if self._recorder:
            self._recorder.cleanup()
            self._recorder = None

        duration_sec = int(time.monotonic() - self._session_start) if self._session_start else 0
        h, rem = divmod(duration_sec, 3600)
        m, s = divmod(rem, 60)
        duration_str = f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"

        from datetime import datetime
        metadata = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "duration": duration_str,
            "chunk_count": self._chunk_count,
            "models_used": "",  # filled by post-stop dialog after model selection
        }
        full_transcript = " ".join(self._chunk_texts)

        if self._on_session_complete:
            self._on_session_complete(full_transcript, metadata)
        return False
