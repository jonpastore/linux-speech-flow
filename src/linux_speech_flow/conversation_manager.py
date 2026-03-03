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
        self._speech_heartbeat_timer: int | None = None
        self._silence_dialog: Gtk.Window | None = None
        self._in_flight: int = 0       # active transcription threads
        self._session_ending: bool = False  # True while draining after stop

        # Silence display accumulation (across chunk boundaries)
        self._silence_offset_sec: int = 0
        self._last_silence_frames: int = -1

    def start_session(self) -> None:
        """Start a new conversation recording session. Called on GTK main thread."""
        if self._state != _STATE_IDLE:
            logger.warning("start_session called but state=%s — ignoring", self._state)
            return
        self._state = _STATE_CONVERSATION
        self._chunk_texts = []
        self._chunk_count = 0
        self._session_start = time.monotonic()
        self._silence_offset_sec = 0
        self._last_silence_frames = -1
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
        silence_rms_threshold = config.get("conv_silence_rms_threshold", 0.005)
        warn_sec = config.get("conv_silence_warn_sec", 30)
        stop_sec = config.get("conv_silence_stop_sec", 60)
        hard_limit = config.get("conv_hard_limit_sec", 14400)

        logger.info(
            "start_session: device=%r chunk_silence=%ds rms_threshold=%.4f "
            "warn=%ds stop=%ds hard_limit=%ds",
            device_name or "default", chunk_silence_sec, silence_rms_threshold,
            warn_sec, stop_sec, hard_limit,
        )

        self._recorder = ConversationRecorder(
            device_name=device_name,
            chunk_silence_sec=chunk_silence_sec,
            silence_rms_threshold=silence_rms_threshold,
        )
        self._recorder.start(
            on_chunk_ready=self._on_chunk_ready,
            on_error=self._on_recorder_error,
            on_silence_tick=self._on_silence_tick,
            on_audio_level=self._on_audio_level,
            on_threshold_calibrated=self._on_threshold_calibrated,
        )

        # Hard limit timer
        self._hard_limit_timer = GLib.timeout_add_seconds(
            hard_limit, self._on_hard_limit
        )
        # Start session silence detection timer immediately
        self._reset_silence_timers(reason="session_start")
        # Heartbeat: every 5s, if user was recently speaking, renew warn timer so
        # continuous speech (no chunk boundaries) doesn't trigger a false warn.
        self._speech_heartbeat_timer = GLib.timeout_add_seconds(
            5, self._on_speech_heartbeat
        )

    def stop_session(self, reason: str = "user") -> None:
        """Stop recording and assemble final transcript. Called on GTK main thread."""
        if self._state != _STATE_CONVERSATION:
            logger.debug("stop_session(%s) ignored — state=%s", reason, self._state)
            return
        elapsed = int(time.monotonic() - self._session_start) if self._session_start else 0
        logger.info(
            "stop_session: reason=%s elapsed=%ds chunks=%d texts=%d",
            reason, elapsed, self._chunk_count, len(self._chunk_texts),
        )
        self._state = _STATE_IDLE
        self._cancel_all_timers()

        self._session_ending = True
        if self._recorder:
            self._recorder.stop()
            # 200ms lets the recorder's final GLib.idle_add(on_chunk_ready) reach
            # the GTK main loop before we check _in_flight.
            GLib.timeout_add(200, self._try_finish_after_stop)
        else:
            self._session_ending = False
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
            self._status_window = ConversationStatusWindow(
                application=self._app,
                on_threshold_changed=self.set_threshold,
            )
        self._status_window.start()
        self._status_window.present()

    def _on_chunk_ready(self, wav_path: str) -> bool:
        """Called on GTK main thread when recorder delivers a chunk."""
        if self._state != _STATE_CONVERSATION and not self._session_ending:
            return False
        self._chunk_count += 1
        self._in_flight += 1
        elapsed = int(time.monotonic() - self._session_start) if self._session_start else 0
        logger.info(
            "chunk_ready: chunk=%d elapsed=%ds wav=%s — resetting silence timers",
            self._chunk_count, elapsed, wav_path,
        )
        self._reset_silence_timers(reason=f"chunk_{self._chunk_count}")
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
            GLib.idle_add(self._on_thread_done)

    def _on_chunk_transcribed(self, text: str, chunk_num: int) -> bool:
        """GTK main thread: store transcribed text."""
        if text:
            self._chunk_texts.append(text)
            logger.info("chunk %d transcribed: %d chars — %r", chunk_num, len(text), text[:80])
        else:
            logger.info("chunk %d transcribed: empty (no speech detected)", chunk_num)
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
        self.stop_session(reason="recorder_error")
        return False

    def set_threshold(self, value: float) -> None:
        """Update silence RMS threshold live. Safe to call from GTK main thread."""
        if self._recorder:
            self._recorder.set_threshold(value)

    def _on_audio_level(self, level: float) -> bool:
        """GTK main thread (via GLib.idle_add): forward mic level to status window."""
        if self._status_window:
            self._status_window.update_mic_level(level)
        return False

    def _on_silence_tick(self, silence_frames: int) -> bool:
        """GTK main thread (via GLib.idle_add): forward silence counter to status window.

        silence_frames is the per-chunk frame count. When a new chunk starts after a
        silence boundary, frames reset to 0. We carry forward the prior silence via
        _silence_offset_sec so the display counts up continuously across chunk boundaries.
        """
        if silence_frames == 0:
            # Voice detected — reset accumulated silence and restart session timers
            # so the warn/stop timers measure inactivity from last speech, not last chunk.
            self._silence_offset_sec = 0
            self._reset_silence_timers(reason="voice_detected")
        elif self._last_silence_frames > silence_frames:
            # frames went backwards (new chunk started after silence boundary)
            self._silence_offset_sec += int(self._last_silence_frames * 0.1)
        self._last_silence_frames = silence_frames
        if self._status_window:
            silence_sec = self._silence_offset_sec + int(silence_frames * 0.1)
            self._status_window.update_silence(silence_sec)
        return False

    def _reset_silence_timers(self, reason: str = "") -> None:
        """Cancel existing session silence timers and start fresh."""
        cancelled = []
        if self._warn_timer:
            GLib.source_remove(self._warn_timer)
            self._warn_timer = None
            cancelled.append("warn")
        if self._stop_timer:
            GLib.source_remove(self._stop_timer)
            self._stop_timer = None
            cancelled.append("stop")
        if self._silence_dialog:
            self._silence_dialog.close()
            self._silence_dialog = None
            cancelled.append("dialog")
        config = load_config()
        warn_sec = config.get("conv_silence_warn_sec", 30)
        stop_sec = config.get("conv_silence_stop_sec", 60)
        now = time.monotonic()
        self._warn_timer = GLib.timeout_add_seconds(warn_sec, self._on_silence_warn)
        if self._status_window:
            self._status_window.set_silence_baseline(now, warn_sec, stop_sec)
        elapsed = int(now - self._session_start) if self._session_start else 0
        logger.info(
            "silence_timers_reset: reason=%s elapsed=%ds warn_in=%ds stop_in=%ds cancelled=%s",
            reason, elapsed, warn_sec, stop_sec, cancelled or "none",
        )

    def _on_silence_warn(self) -> bool:
        """Session-level silence warn threshold reached: show continue/stop dialog."""
        self._warn_timer = None
        config = load_config()
        stop_sec = config.get("conv_silence_stop_sec", 60)
        warn_sec = config.get("conv_silence_warn_sec", 30)
        extra = max(stop_sec - warn_sec, 5)
        elapsed = int(time.monotonic() - self._session_start) if self._session_start else 0
        logger.info(
            "silence_warn_fired: elapsed=%ds warn_sec=%d stop_sec=%d extra_until_autostop=%ds",
            elapsed, warn_sec, stop_sec, extra,
        )
        self._show_silence_modal()
        self._stop_timer = GLib.timeout_add_seconds(extra, self._on_silence_autostop)
        logger.info("silence_autostop_scheduled: fires_in=%ds", extra)
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

        def _close_dialog():
            if self._silence_dialog:
                self._silence_dialog.close()
                self._silence_dialog = None

        stop_btn = Gtk.Button(label="Stop Recording")
        stop_btn.connect("clicked", lambda _b: (
            logger.info("silence_dialog: user clicked Stop Recording"),
            _close_dialog(), self.stop_session(reason="silence_dialog_stop"),
        ))
        btn_box.append(stop_btn)

        continue_btn = Gtk.Button(label="Continue")
        continue_btn.add_css_class("suggested-action")
        continue_btn.connect("clicked", lambda _b: (
            logger.info("silence_dialog: user clicked Continue"),
            _close_dialog(), self._reset_silence_timers(reason="silence_dialog_continue"),
        ))
        btn_box.append(continue_btn)

        self._silence_dialog = dialog
        dialog.present()

    def _on_silence_autostop(self) -> bool:
        """Auto-stop after silence stop threshold: close warn dialog and stop."""
        self._stop_timer = None
        elapsed = int(time.monotonic() - self._session_start) if self._session_start else 0
        logger.info("silence_autostop_fired: elapsed=%ds — closing dialog and stopping", elapsed)
        if self._silence_dialog:
            self._silence_dialog.close()
            self._silence_dialog = None
        config = load_config()
        play_sound("stop.wav",
                   output_device=config.get("sounds_output_device", ""),
                   enabled=config.get("sounds_enabled", True))
        self.stop_session(reason="silence_autostop")
        return False

    def _on_hard_limit(self) -> bool:
        """Hard recording time limit reached: stop session."""
        self._hard_limit_timer = None
        elapsed = int(time.monotonic() - self._session_start) if self._session_start else 0
        logger.info("hard_limit_fired: elapsed=%ds", elapsed)
        config = load_config()
        play_sound("error.wav",
                   output_device=config.get("sounds_output_device", ""),
                   enabled=config.get("sounds_enabled", True))
        self.stop_session(reason="hard_limit")
        return False

    def _on_speech_heartbeat(self) -> bool:
        """GTK main thread: every 5s during a session, if user is actively speaking
        (last known silence_frames == 0), renew the warn timer and visual baseline.

        This prevents false silence-warn during uninterrupted long speech where no
        chunk boundary fires (chunks only emit after chunk_silence_sec of silence)
        and where the on_silence_tick(0) transition already fired at speech start
        but is debounced and won't fire again until next silence→speech transition.
        """
        if self._state != _STATE_CONVERSATION:
            return False
        if self._last_silence_frames == 0:
            # User is actively speaking — renew session silence timers
            config = load_config()
            warn_sec = config.get("conv_silence_warn_sec", 30)
            stop_sec = config.get("conv_silence_stop_sec", 60)
            if self._warn_timer:
                GLib.source_remove(self._warn_timer)
            self._warn_timer = GLib.timeout_add_seconds(warn_sec, self._on_silence_warn)
            if self._status_window:
                self._status_window.set_silence_baseline(time.monotonic(), warn_sec, stop_sec)
            logger.debug("speech_heartbeat: user speaking — renewed warn timer warn_in=%ds", warn_sec)
        return True

    def _on_thread_done(self) -> bool:
        """GTK main thread: called when a transcription thread finishes."""
        self._in_flight = max(0, self._in_flight - 1)
        logger.debug("thread_done: in_flight=%d session_ending=%s", self._in_flight, self._session_ending)
        if self._in_flight == 0 and self._session_ending:
            self._session_ending = False
            self._finish_session()
        return False

    def _try_finish_after_stop(self) -> bool:
        """GTK main thread: called 200ms after stop to check if all threads are done."""
        if self._in_flight == 0:
            self._session_ending = False
            self._finish_session()
        # else: _on_thread_done will call _finish_session when last thread completes
        return False

    def _on_threshold_calibrated(self, value: float) -> bool:
        """GTK main thread: auto-calibration set a new silence threshold."""
        logger.info("threshold_calibrated: %.5f", value)
        if self._status_window:
            self._status_window.set_threshold_from_calibration(value)
        return False

    def _cancel_all_timers(self) -> None:
        for attr in ('_warn_timer', '_stop_timer', '_hard_limit_timer', '_speech_heartbeat_timer'):
            tid = getattr(self, attr)
            if tid:
                GLib.source_remove(tid)
                setattr(self, attr, None)

    def _finish_session(self) -> bool:
        """Assemble final transcript and fire on_session_complete. GTK main thread."""
        self._session_ending = False
        logger.info(
            "finish_session: assembling transcript from %d chunk(s)", len(self._chunk_texts)
        )
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
        logger.info(
            "finish_session: transcript=%d chars duration=%s — firing on_session_complete",
            len(full_transcript), duration_str,
        )

        if self._on_session_complete:
            self._on_session_complete(full_transcript, metadata)
        return False
