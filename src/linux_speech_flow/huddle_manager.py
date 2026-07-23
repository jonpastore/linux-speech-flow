import logging
import math
import re
import struct
import threading
import time
import wave
from datetime import datetime

from gi.repository import GLib

from linux_speech_flow import llm_router
from linux_speech_flow.config import load_config
from linux_speech_flow.huddle_recorder import HuddleRecorder
from linux_speech_flow.notify import send_notification

logger = logging.getLogger(__name__)

_COMMANDS = [
    "start recording",
    "stop recording",
    "list action items",
    "pause",
    "resume",
    "summarize",
    "calibrate",
    "status",
    "help",
    "debug",
]

_DEBUG_LEVELS = ("low", "medium", "high")

# Short aliases mapped to canonical command keys
_ALIASES = {
    "stop": "stop recording",
    "start": "start recording",
}


def _make_welcome_message(word: str) -> str:
    return (
        f"Hi, I'm recording this huddle.\n"
        f"Available commands (say '{word}' followed by):\n"
        f"  start recording / stop recording\n"
        f"  pause / resume\n"
        f"  summarize\n"
        f"  list action items\n"
        f"  calibrate\n"
        f"  status\n"
        f"  note [text]\n"
        f"  topic [title]\n"
        f"  help\n"
        f"Short aliases: '{word} stop' = stop recording, '{word} start' = start recording"
    )


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for command matching."""
    return re.sub(r"[^\w\s]", " ", text.lower())


def _wav_avg_rms(wav_path: str) -> float:
    """Return the average RMS energy of a WAV file (0.0–1.0 normalised).

    Returns 0.0 on any read error so the caller can safely skip the file.
    """
    try:
        with wave.open(wav_path, "rb") as wf:
            n_frames = wf.getnframes()
            if n_frames == 0:
                return 0.0
            raw = wf.readframes(n_frames)
            sample_width = wf.getsampwidth()
            if sample_width == 2:
                fmt = f"{len(raw) // 2}h"
                samples = struct.unpack(fmt, raw)
                rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0
                return rms
    except Exception:
        pass
    return 0.0


def detect_activation(text: str, word: str) -> tuple[str | None, str | None]:
    """Scan transcript text for activation word followed by a command.

    Strips punctuation and normalizes case before matching so that
    transcriptions like 'Lucifer, stop recording.' are correctly detected
    even when the command appears mid-chunk after other speech.

    Returns (command_key, remainder_text) or (None, None) if no match.
    command_key is one of the _COMMANDS list, 'note', 'topic', or an alias target.
    """
    normalized = _normalize(text)
    pattern = re.compile(
        rf"\b{re.escape(_normalize(word).strip())}\b\s+(.*)",
        re.IGNORECASE,
    )
    m = pattern.search(normalized)
    if not m:
        return None, None
    remainder = m.group(1).strip()
    for cmd in sorted(_COMMANDS, key=len, reverse=True):
        if remainder.startswith(cmd):
            after = remainder[len(cmd) :].strip()
            return cmd, after
    for alias, canonical in _ALIASES.items():
        if remainder == alias or remainder.startswith(alias + " "):
            after = remainder[len(alias) :].strip()
            return canonical, after
    if remainder.startswith("note "):
        return "note", remainder[5:].strip()
    if remainder.startswith("topic "):
        return "topic", remainder[6:].strip()
    return None, None


class HuddleManager:
    """Orchestrates Slack huddle recording sessions.

    Threading contract:
    - start_session() / stop_session() called on GTK main thread.
    - Per-chunk Whisper transcription runs in daemon threads.
    - Chunk callbacks dispatched via GLib.idle_add (GTK main thread).
    - All GTK / HuddleStatusWindow operations from GTK main thread only.
    - on_session_complete fires on GTK main thread.
    """

    def __init__(
        self,
        application,
        slack_manager,
        on_session_complete,
        on_tray_state,
        on_analyze=None,
    ):
        """
        Args:
            application: Gtk.Application (for HuddleStatusWindow creation)
            slack_manager: SlackManager instance
            on_session_complete: Callable(transcript, metadata) fired on session end
            on_tray_state: Callable(state: str) -- 'huddle' or 'idle'
            on_analyze: Optional Callable(transcript, metadata) to open mid-session analysis
        """
        self._app = application
        self._slack_manager = slack_manager
        self._on_session_complete = on_session_complete
        self._on_tray_state = on_tray_state
        self._on_analyze = on_analyze
        self._recorder: HuddleRecorder | None = None
        self._status_window = None
        self._chunk_texts: list[str] = []
        self._chunk_count = 0
        self._in_flight = 0
        self._session_ending = False
        self._session_finished = False
        self._drain_start: float | None = None
        self._active_team_id: str | None = None
        self._active_channel_id: str | None = None
        self._session_start: float | None = None
        self._paused = False
        self._debug_level: str | None = None
        self._chunk_near_silence_threshold: float = 0.005

    def is_active(self) -> bool:
        """Return True if a huddle session is in progress."""
        return self._recorder is not None

    def _debug_post(self, message: str, level: str = "low") -> None:
        """Post a debug message to Slack if debug is enabled at or above the given level.

        Safe to call from any thread — posts via background thread.
        """
        if self._debug_level is None:
            return
        if _DEBUG_LEVELS.index(level) > _DEBUG_LEVELS.index(self._debug_level):
            return
        team_id = self._active_team_id
        channel_id = self._active_channel_id
        if team_id and channel_id:
            threading.Thread(
                target=self._slack_manager.post_message,
                args=(
                    team_id,
                    channel_id,
                    f"\U0001f527 [DEBUG/{level.upper()}] {message}",
                ),
                daemon=True,
            ).start()

    def trigger_analyze(self) -> None:
        """GTK main thread: pause transcript collection and open mid-session analysis dialog."""
        if not self._on_analyze:
            return
        self._paused = True
        if self._status_window:
            self._status_window.update_pause_state(True)
        snapshot = "\n".join(self._chunk_texts)
        metadata = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "duration": "(ongoing)",
            "chunk_count": self._chunk_count,
            "models_used": "",
            "team_id": self._active_team_id,
            "channel_id": self._active_channel_id,
        }
        team_id = self._active_team_id
        channel_id = self._active_channel_id
        if team_id and channel_id:
            threading.Thread(
                target=self._slack_manager.post_message,
                args=(
                    team_id,
                    channel_id,
                    "\u23f8\ufe0f Recording paused for analysis",
                ),
                daemon=True,
            ).start()
        self._debug_post(
            "trigger_analyze: recording paused, opening analysis dialog", "medium"
        )
        self._on_analyze(snapshot, metadata)

    def resume_from_analyze(self) -> None:
        """GTK main thread: resume transcript collection after analysis dialog closed."""
        self._paused = False
        if self._status_window:
            self._status_window.update_pause_state(False)
        team_id = self._active_team_id
        channel_id = self._active_channel_id
        if team_id and channel_id:
            threading.Thread(
                target=self._slack_manager.post_message,
                args=(team_id, channel_id, "\u25b6\ufe0f Recording resumed"),
                daemon=True,
            ).start()
        self._debug_post("resume_from_analyze: recording resumed", "medium")

    def _on_ui_pause(self) -> None:
        """GTK main thread: Pause button clicked in status window."""
        self._paused = True
        if self._status_window:
            self._status_window.update_pause_state(True)
        team_id = self._active_team_id
        channel_id = self._active_channel_id
        if team_id and channel_id:
            threading.Thread(
                target=self._slack_manager.post_message,
                args=(
                    team_id,
                    channel_id,
                    "\u23f8\ufe0f Recording paused (transcript collection suspended)",
                ),
                daemon=True,
            ).start()
        self._debug_post("paused via UI button", "medium")

    def _on_ui_resume(self) -> None:
        """GTK main thread: Resume button clicked in status window."""
        self._paused = False
        if self._status_window:
            self._status_window.update_pause_state(False)
        team_id = self._active_team_id
        channel_id = self._active_channel_id
        if team_id and channel_id:
            threading.Thread(
                target=self._slack_manager.post_message,
                args=(team_id, channel_id, "\u25b6\ufe0f Recording resumed"),
                daemon=True,
            ).start()
        self._debug_post("resumed via UI button", "medium")

    def start_session(self, team_id: str, channel_id: str) -> None:
        """Start a huddle recording session. Called on GTK main thread."""
        if self._recorder is not None:
            logger.warning("start_session called but already active — ignoring")
            return

        config = load_config()
        self._active_team_id = team_id
        self._active_channel_id = channel_id
        self._chunk_texts = []
        self._chunk_count = 0
        self._in_flight = 0
        self._session_ending = False
        self._session_finished = False
        self._drain_start = None
        self._paused = False
        self._session_start = time.monotonic()

        mic_device = config.get("microphone", "")
        chunk_silence_sec = config.get("conv_chunk_silence_sec", 3)
        silence_rms_threshold = config.get("conv_silence_rms_threshold", 0.005)
        self._chunk_near_silence_threshold = silence_rms_threshold

        self._recorder = HuddleRecorder(
            mic_device=mic_device or None,
            chunk_silence_sec=chunk_silence_sec,
            silence_rms_threshold=silence_rms_threshold,
        )

        from linux_speech_flow.huddle_status import HuddleStatusWindow

        self._status_window = HuddleStatusWindow(
            application=self._app,
            on_threshold_changed=self._on_threshold_changed,
        )
        self._status_window.set_on_analyze(self.trigger_analyze)

        self._recorder.start(
            on_chunk_ready=self._on_chunk_ready,
            on_error=self._on_recorder_error,
            on_audio_level=self._on_audio_level,
            on_threshold_calibrated=self._on_threshold_calibrated,
        )
        self._status_window.set_on_pause(self._on_ui_pause)
        self._status_window.set_on_resume(self._on_ui_resume)
        self._status_window.set_on_stop(self.stop_session)
        self._status_window.set_on_exit(
            lambda: self._debug_post(
                "status window dismissed — session continues", "medium"
            )
        )
        self._status_window.present()
        self._status_window.start_elapsed_timer()

        workspaces = self._slack_manager.get_workspaces()
        ws = workspaces.get(team_id, {})
        team_name = ws.get("team_name", "")
        self._status_window.update_slack_status(True, team_name, channel_id)

        if self._on_tray_state:
            self._on_tray_state("huddle")

        threading.Thread(
            target=self._post_welcome,
            args=(team_id, channel_id),
            daemon=True,
        ).start()

    def debug_post(self, message: str, level: str = "medium") -> None:
        """Public wrapper for _debug_post — allows app.py to post debug messages."""
        self._debug_post(message, level)

    def stop_session(self) -> None:
        """Stop huddle recording. Called on GTK main thread."""
        if self._recorder is None:
            logger.debug("stop_session called but no active session")
            return

        self._debug_post("recording stopped — waiting for in-flight chunks", "medium")
        self._session_ending = True

        recorder = self._recorder
        self._recorder = None
        recorder.stop()

        if self._status_window:
            self._status_window.stop_elapsed_timer()
            self._status_window.close()
            self._status_window = None

        if self._on_tray_state:
            self._on_tray_state("idle")

        if self._in_flight == 0:
            self._finish_session()
        else:
            self._drain_start = time.monotonic()
            GLib.timeout_add(500, self._drain_check)

    _DRAIN_TIMEOUT_SEC = 90

    def _drain_check(self) -> bool:
        """GTK main thread: called every 500ms while waiting for in-flight threads."""
        if self._in_flight == 0:
            if self._session_ending:
                self._session_ending = False
                self._finish_session()
            return False
        if (
            self._drain_start
            and time.monotonic() - self._drain_start > self._DRAIN_TIMEOUT_SEC
        ):
            logger.warning(
                "Drain timeout — forcing session finish with %d in-flight chunks",
                self._in_flight,
            )
            self._debug_post(
                f"drain timeout — forcing finish ({self._in_flight} chunk(s) still in flight)",
                "medium",
            )
            self._in_flight = 0
            self._session_ending = False
            self._finish_session()
            return False
        return True

    def _on_chunk_ready(self, wav_path: str) -> bool:
        """Called on GTK main thread (via GLib.idle_add from HuddleRecorder)."""
        self._in_flight += 1
        self._chunk_count += 1

        if self._status_window:
            self._status_window.update_chunk_count(self._chunk_count)

        config = load_config()
        team_id = self._active_team_id
        channel_id = self._active_channel_id

        threading.Thread(
            target=self._transcribe_chunk,
            args=(wav_path, team_id, channel_id, config),
            daemon=True,
        ).start()
        return False

    def _transcribe_chunk(
        self, wav_path: str, team_id: str, channel_id: str, config: dict
    ) -> None:
        """Worker thread: transcribe chunk and dispatch result."""
        try:
            silence_threshold = self._chunk_near_silence_threshold
            avg_rms = _wav_avg_rms(wav_path)
            if avg_rms < silence_threshold:
                logger.info(
                    "Skipping near-silence chunk (avg_rms=%.5f < threshold=%.5f): %s",
                    avg_rms,
                    silence_threshold,
                    wav_path,
                )
                return

            client, model = llm_router.transcription_client_model(config)

            with open(wav_path, "rb") as f:
                response = client.audio.transcriptions.create(
                    file=("chunk.wav", f),
                    model=model,
                    response_format="verbose_json",
                )
            text = response.text or ""
            segments = getattr(response, "segments", None) or []
            if segments:
                avg_logprob = sum(
                    s.get("avg_logprob", 0) if isinstance(s, dict) else s.avg_logprob
                    for s in segments
                ) / len(segments)
                confidence = max(0.0, min(1.0, 1.0 + avg_logprob))
            else:
                confidence = 1.0

            activation_word = config.get("slack_activation_word", "conyo")
            cmd_key, remainder = detect_activation(text, activation_word)

            if cmd_key is not None:
                GLib.idle_add(
                    self._dispatch_command,
                    cmd_key,
                    remainder or "",
                    team_id,
                    channel_id,
                    config,
                )
            else:
                if text and not self._paused:
                    self._chunk_texts.append(text)
                GLib.idle_add(
                    self._on_chunk_transcribed,
                    text,
                    confidence,
                    team_id,
                    channel_id,
                    config,
                )

        except Exception as exc:
            logger.error("Transcription error: %s", exc)
        finally:
            try:
                import os

                os.unlink(wav_path)
            except OSError:
                pass
            GLib.idle_add(self._on_in_flight_done)

    def _on_chunk_transcribed(
        self, text: str, confidence: float, team_id: str, channel_id: str, config: dict
    ) -> bool:
        """GTK main thread: update status window and check confidence threshold."""
        if self._status_window:
            self._status_window.update_transcript(text)
            self._status_window.update_confidence(confidence)

        threshold = config.get("slack_confidence_threshold", 0.6)
        if confidence < threshold:
            threading.Thread(
                target=self._post_confidence_alert,
                args=(team_id, channel_id),
                daemon=True,
            ).start()
        if text and self._debug_level == "high":
            snippet = text[:80] + ("…" if len(text) > 80 else "")
            pct = int(confidence * 100)
            self._debug_post(
                f"chunk #{self._chunk_count} conf={pct}% paused={self._paused} | {snippet!r}",
                "high",
            )
        return False

    def _dispatch_command(
        self, cmd_key: str, remainder: str, team_id: str, channel_id: str, config: dict
    ) -> bool:
        """GTK main thread: execute a voice command."""
        word = config.get("slack_activation_word", "conyo")
        display = f"{word} {cmd_key}" + (f" {remainder}" if remainder else "")
        if self._status_window:
            self._status_window.update_last_command(display)
            self._status_window.set_command_processing(True)
        self._debug_post(
            f"Command: '{cmd_key}'" + (f" args='{remainder}'" if remainder else ""),
            "low",
        )

        def _run_command():
            try:
                self._execute_command(cmd_key, remainder, team_id, channel_id, config)
            finally:
                GLib.idle_add(self._command_done)

        threading.Thread(target=_run_command, daemon=True).start()
        return False

    def _command_done(self) -> bool:
        if self._status_window:
            self._status_window.set_command_processing(False)
        return False

    def _execute_command(
        self, cmd_key: str, remainder: str, team_id: str, channel_id: str, config: dict
    ) -> None:
        """Worker thread: implement each voice command."""
        if cmd_key == "stop recording":
            self._debug_post("stop recording → stopping session", "medium")
            GLib.idle_add(self.stop_session)

        elif cmd_key == "pause":
            self._paused = True
            GLib.idle_add(
                lambda: (
                    self._status_window.update_pause_state(True)
                    if self._status_window
                    else None
                )
            )
            self._slack_manager.post_message(
                team_id,
                channel_id,
                "\u23f8\ufe0f Recording paused (transcript collection suspended)",
            )
            self._debug_post(
                "paused — chunks will be transcribed but excluded from transcript",
                "medium",
            )
            logger.info(
                "Huddle paused — audio still captured, chunks excluded from transcript"
            )

        elif cmd_key == "resume":
            self._paused = False
            GLib.idle_add(
                lambda: (
                    self._status_window.update_pause_state(False)
                    if self._status_window
                    else None
                )
            )
            self._slack_manager.post_message(
                team_id, channel_id, "\u25b6\ufe0f Recording resumed"
            )
            self._debug_post("resumed — chunks included in transcript again", "medium")
            logger.info("Huddle resumed — chunks included in transcript again")

        elif cmd_key == "summarize":
            transcript = "\n".join(self._chunk_texts)
            if not transcript.strip():
                self._slack_manager.post_message(
                    team_id, channel_id, "No transcript yet to summarize."
                )
                self._debug_post("summarize: no transcript yet", "low")
                return
            self._debug_post(
                f"summarize: calling LLM on {len(self._chunk_texts)} chunks", "medium"
            )
            summary = self._call_llm_summary(transcript, config)
            if summary:
                self._slack_manager.post_message(
                    team_id, channel_id, f"*Summary:*\n{summary}"
                )
                self._debug_post("summarize: posted to channel", "low")

        elif cmd_key == "list action items":
            transcript = "\n".join(self._chunk_texts)
            if not transcript.strip():
                self._slack_manager.post_message(
                    team_id, channel_id, "No transcript yet."
                )
                self._debug_post("list action items: no transcript yet", "low")
                return
            self._debug_post(
                f"list action items: calling LLM on {len(self._chunk_texts)} chunks",
                "medium",
            )
            items = self._call_llm_action_items(transcript, config)
            if items:
                self._slack_manager.post_message(
                    team_id, channel_id, f"*Action Items:*\n{items}"
                )
                self._debug_post("list action items: posted to channel", "low")

        elif cmd_key == "calibrate":
            self._slack_manager.post_message(
                team_id, channel_id, "Please speak one at a time and closer to your mic"
            )
            self._debug_post("calibrate: message posted", "low")

        elif cmd_key == "status":
            elapsed = (
                int(time.monotonic() - self._session_start)
                if self._session_start
                else 0
            )
            m, s = divmod(elapsed, 60)
            h, m = divmod(m, 60)
            if h:
                duration_str = f"{h}h {m:02d}m {s:02d}s"
            else:
                duration_str = f"{m}m {s:02d}s"
            paused_str = " | PAUSED" if self._paused else ""
            debug_str = (
                f" | debug={self._debug_level or 'off'}" if self._debug_level else ""
            )
            self._slack_manager.post_message(
                team_id,
                channel_id,
                f"Recording duration: {duration_str} | Chunks: {self._chunk_count}{paused_str}{debug_str}",
            )

        elif cmd_key == "note":
            note_text = f"[NOTE: {remainder}]"
            self._chunk_texts.append(note_text)
            self._slack_manager.post_message(team_id, channel_id, note_text)
            self._debug_post(f"note added: {remainder}", "medium")

        elif cmd_key == "topic":
            topic_text = f"\n## {remainder}\n"
            self._chunk_texts.append(topic_text)
            self._slack_manager.post_message(
                team_id, channel_id, f"*Topic:* {remainder}"
            )
            self._debug_post(f"topic set: {remainder}", "medium")

        elif cmd_key == "help":
            word = config.get("slack_activation_word", "conyo")
            self._slack_manager.post_message(
                team_id, channel_id, _make_welcome_message(word)
            )

        elif cmd_key == "debug":
            sub = remainder.strip().lower()
            _descriptions = {
                "low": "commands + errors",
                "medium": "low + state changes + LLM calls",
                "high": "medium + per-chunk confidence + transcript snippets",
            }
            if sub in ("off",):
                self._debug_level = None
                self._slack_manager.post_message(
                    team_id, channel_id, "\U0001f527 Debug mode: OFF"
                )
            elif sub in ("on", ""):
                self._debug_level = "low"
                self._slack_manager.post_message(
                    team_id,
                    channel_id,
                    f"\U0001f527 Debug mode: LOW ({_descriptions['low']})",
                )
            elif sub in _DEBUG_LEVELS:
                self._debug_level = sub
                self._slack_manager.post_message(
                    team_id,
                    channel_id,
                    f"\U0001f527 Debug mode: {sub.upper()} ({_descriptions[sub]})",
                )
            else:
                self._slack_manager.post_message(
                    team_id,
                    channel_id,
                    "\U0001f527 Usage: debug on/off/low/medium/high",
                )

        elif cmd_key == "start recording":
            logger.warning(
                "'start recording' command received but session already active — ignoring"
            )
            self._debug_post("start recording: ignored — session already active", "low")

        else:
            logger.warning("Unknown command: %s", cmd_key)

    def _call_llm_summary(self, transcript: str, config: dict) -> str:
        """Worker thread: call Groq LLM to summarize the transcript."""
        try:
            client, model = llm_router.chat_client_model(
                config,
                config.get(
                    "conv_groq_model", "meta-llama/llama-4-scout-17b-16e-instruct"
                ),
            )
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize the following meeting transcript concisely.",
                    },
                    {"role": "user", "content": transcript},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.error("LLM summary failed: %s", exc)
            return ""

    def _call_llm_action_items(self, transcript: str, config: dict) -> str:
        """Worker thread: call Groq LLM to extract action items."""
        try:
            client, model = llm_router.chat_client_model(
                config,
                config.get(
                    "conv_groq_model", "meta-llama/llama-4-scout-17b-16e-instruct"
                ),
            )
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "Extract action items from this meeting transcript. List each as a bullet point with owner if identifiable.",
                    },
                    {"role": "user", "content": transcript},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.error("LLM action items failed: %s", exc)
            return ""

    def _post_welcome(self, team_id: str, channel_id: str) -> None:
        """Worker thread: post welcome message to Slack channel."""
        config = load_config()
        word = config.get("slack_activation_word", "conyo")
        self._slack_manager.post_message(
            team_id, channel_id, _make_welcome_message(word)
        )

    def _post_confidence_alert(self, team_id: str, channel_id: str) -> None:
        """Worker thread: post low-confidence alert."""
        self._slack_manager.post_message(
            team_id,
            channel_id,
            "Having trouble understanding \u2014 please try speaking one at a time",
        )
        send_notification(
            "Low transcription confidence in huddle", body="Check Slack for alert"
        )

    def _on_audio_level(self, level: float) -> bool:
        """GTK main thread (via GLib.idle_add): forward mic level to status window."""
        if self._status_window:
            self._status_window.update_mic_level(level)
        return False

    def _on_threshold_calibrated(self, value: float) -> bool:
        """GTK main thread: auto-calibration set a new silence threshold."""
        logger.info("huddle threshold_calibrated: %.5f", value)
        self._chunk_near_silence_threshold = value
        if self._status_window:
            self._status_window.set_threshold_from_calibration(value)
        return False

    def _on_threshold_changed(self, value: float) -> None:
        """Called when user moves the threshold slider in HuddleStatusWindow."""
        if self._recorder:
            self._recorder.set_threshold(value)

    def _on_in_flight_done(self) -> bool:
        """GTK main thread: called when a transcription thread completes."""
        self._in_flight = max(0, self._in_flight - 1)
        if self._in_flight == 0 and self._session_ending:
            self._session_ending = False
            self._finish_session()
        return False

    def _on_recorder_error(self, message: str) -> bool:
        """GTK main thread: recorder error."""
        logger.error("HuddleRecorder error: %s", message)
        self.stop_session()
        return False

    def post_huddle_results(
        self,
        team_id: str,
        channel_id: str,
        result: dict,
        saved_path: str | None,
    ) -> None:
        """Post analysis results to Slack. Always runs on a background thread.

        result dict keys (from ConversationPipeline/ConversationDialog output):
          - 'title': AI-generated title string
          - 'summary': executive summary text
          - 'analysis': full AI analysis text
          - 'date': ISO8601 date string

        Posting failure shows error notification. Local file is always saved
        regardless of Slack post success (caller handles save, we only post).
        """
        from datetime import datetime

        from linux_speech_flow.notify import send_notification

        title = result.get("title") or "Huddle"
        summary = result.get("summary") or ""
        analysis = result.get("analysis") or ""
        date_str = result.get("date") or datetime.now().strftime("%A, %B %d %Y")

        header = f"Huddle on {date_str} about: {title}"
        blocks = self._build_huddle_result_blocks(header, summary, analysis)

        ok = self._slack_manager.post_message(
            team_id=team_id,
            channel_id=channel_id,
            text=header,
            blocks=blocks,
        )
        if not ok:
            GLib.idle_add(
                lambda: send_notification(
                    "Slack post failed",
                    body="Could not post huddle results to Slack. Local file saved.",
                )
            )
            return

        if saved_path:
            upload_ok = self._slack_manager.upload_file(
                team_id=team_id,
                channel_id=channel_id,
                file_path=saved_path,
                title=f"Huddle Transcript — {date_str}",
            )
            if not upload_ok:
                GLib.idle_add(
                    lambda: send_notification(
                        "Slack upload failed",
                        body="Results message posted but transcript file upload failed.",
                    )
                )

    @staticmethod
    def _build_huddle_result_blocks(
        header: str, summary: str, analysis: str
    ) -> list[dict]:
        """Build Slack Block Kit rich message for post-huddle results."""
        return [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Executive Summary*\n{summary}"},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*AI Analysis*\n{analysis}"},
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "_Full transcript attached as .md file_",
                    },
                ],
            },
        ]

    def _finish_session(self) -> None:
        """GTK main thread: assemble final transcript and fire on_session_complete."""
        if self._session_finished:
            logger.debug("_finish_session: already called — skipping duplicate")
            return
        self._session_finished = True
        self._session_ending = False
        full_transcript = "\n".join(self._chunk_texts)
        elapsed = (
            int(time.monotonic() - self._session_start) if self._session_start else 0
        )
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        duration_str = f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"

        metadata = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "duration": duration_str,
            "chunk_count": self._chunk_count,
            "models_used": "",
            "session_type": "huddle",
            "team_id": self._active_team_id,
            "channel_id": self._active_channel_id,
        }

        if self._recorder:
            self._recorder.cleanup()
            self._recorder = None

        self._debug_post(
            f"session complete — {self._chunk_count} chunk(s), opening analysis dialog",
            "medium",
        )
        if self._on_session_complete:
            self._on_session_complete(full_transcript, metadata)
