import logging
import re
import threading
import time
from datetime import datetime

from gi.repository import GLib

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
]

WELCOME_MESSAGE = (
    "Hi, I'm recording this huddle.\n"
    "Available commands:\n"
    "  conyo start/stop recording | conyo pause/resume | conyo summarize\n"
    "  conyo calibrate | conyo status | conyo list action items\n"
    "  conyo note [text] | conyo topic [title] | conyo help\n"
    "(Replace 'conyo' with your configured activation word.)"
)


def detect_activation(text: str, word: str) -> tuple[str | None, str | None]:
    """Scan transcript text for activation word followed by a command.

    Returns (command_key, remainder_text) or (None, None) if no match.
    command_key is one of the _COMMANDS list, 'note', or 'topic'.
    """
    pattern = re.compile(
        rf'\b{re.escape(word.lower())}\s+(.+)',
        re.IGNORECASE,
    )
    m = pattern.search(text.lower())
    if not m:
        return None, None
    remainder = m.group(1).strip()
    for cmd in sorted(_COMMANDS, key=len, reverse=True):
        if remainder.startswith(cmd):
            after = remainder[len(cmd):].strip()
            return cmd, after
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

    def __init__(self, application, slack_manager, on_session_complete, on_tray_state):
        """
        Args:
            application: Gtk.Application (for HuddleStatusWindow creation)
            slack_manager: SlackManager instance
            on_session_complete: Callable(transcript, metadata) fired on session end
            on_tray_state: Callable(state: str) -- 'huddle' or 'idle'
        """
        self._app = application
        self._slack_manager = slack_manager
        self._on_session_complete = on_session_complete
        self._on_tray_state = on_tray_state
        self._recorder: HuddleRecorder | None = None
        self._status_window = None
        self._chunk_texts: list[str] = []
        self._chunk_count = 0
        self._in_flight = 0
        self._session_ending = False
        self._active_team_id: str | None = None
        self._active_channel_id: str | None = None
        self._session_start: float | None = None
        self._paused = False

    def is_active(self) -> bool:
        """Return True if a huddle session is in progress."""
        return self._recorder is not None

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
        self._paused = False
        self._session_start = time.monotonic()

        mic_device = config.get("microphone", "")
        chunk_silence_sec = config.get("conv_chunk_silence_sec", 3)
        silence_rms_threshold = config.get("conv_silence_rms_threshold", 0.005)

        self._recorder = HuddleRecorder(
            mic_device=mic_device or None,
            chunk_silence_sec=chunk_silence_sec,
            silence_rms_threshold=silence_rms_threshold,
        )
        self._recorder.start(
            on_chunk_ready=self._on_chunk_ready,
            on_error=self._on_recorder_error,
        )

        from linux_speech_flow.huddle_status import HuddleStatusWindow
        self._status_window = HuddleStatusWindow(application=self._app)
        self._status_window.present()
        self._status_window.start_elapsed_timer()

        workspaces = self._slack_manager.get_workspaces()
        ws = workspaces.get(team_id, {})
        team_name = ws.get("team_name", "")
        self._status_window.update_slack_status(True, team_name, channel_id)

        if self._on_tray_state:
            self._on_tray_state('huddle')

        threading.Thread(
            target=self._post_welcome,
            args=(team_id, channel_id),
            daemon=True,
        ).start()

    def stop_session(self) -> None:
        """Stop huddle recording. Called on GTK main thread."""
        if self._recorder is None:
            logger.debug("stop_session called but no active session")
            return

        self._session_ending = True

        recorder = self._recorder
        self._recorder = None
        recorder.stop()

        if self._status_window:
            self._status_window.stop_elapsed_timer()
            self._status_window.close()
            self._status_window = None

        if self._on_tray_state:
            self._on_tray_state('idle')

        if self._in_flight == 0:
            self._finish_session()
        else:
            GLib.timeout_add(500, self._drain_check)

    def _drain_check(self) -> bool:
        """GTK main thread: called every 500ms while waiting for in-flight threads."""
        if self._in_flight == 0:
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

    def _transcribe_chunk(self, wav_path: str, team_id: str, channel_id: str, config: dict) -> None:
        """Worker thread: transcribe chunk and dispatch result."""
        try:
            from groq import Groq
            api_key = config.get("groq_api_key", "")
            groq_client = Groq(api_key=api_key, max_retries=0)

            with open(wav_path, "rb") as f:
                response = groq_client.audio.transcriptions.create(
                    file=("chunk.wav", f),
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json",
                )
            text = response.text or ""
            segments = getattr(response, "segments", None) or []
            if segments:
                avg_logprob = sum(s.avg_logprob for s in segments) / len(segments)
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
                if text:
                    self._chunk_texts.append(text)
                GLib.idle_add(self._on_chunk_transcribed, text, confidence, team_id, channel_id, config)

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
        return False

    def _dispatch_command(
        self, cmd_key: str, remainder: str, team_id: str, channel_id: str, config: dict
    ) -> bool:
        """GTK main thread: execute a voice command."""
        if self._status_window:
            self._status_window.update_last_command(f"{config.get('slack_activation_word', 'conyo')} {cmd_key}")
            self._status_window.set_command_processing(True)

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
            GLib.idle_add(self.stop_session)

        elif cmd_key == "pause":
            self._paused = True
            if self._recorder:
                self._recorder.pause()

        elif cmd_key == "resume":
            self._paused = False
            if self._recorder:
                self._recorder.resume()

        elif cmd_key == "summarize":
            transcript = "\n".join(self._chunk_texts)
            if not transcript.strip():
                self._slack_manager.post_message(team_id, channel_id, "No transcript yet to summarize.")
                return
            summary = self._call_llm_summary(transcript, config)
            if summary:
                self._slack_manager.post_message(team_id, channel_id, f"*Summary:*\n{summary}")

        elif cmd_key == "list action items":
            transcript = "\n".join(self._chunk_texts)
            if not transcript.strip():
                self._slack_manager.post_message(team_id, channel_id, "No transcript yet.")
                return
            items = self._call_llm_action_items(transcript, config)
            if items:
                self._slack_manager.post_message(team_id, channel_id, f"*Action Items:*\n{items}")

        elif cmd_key == "calibrate":
            self._slack_manager.post_message(
                team_id, channel_id,
                "Please speak one at a time and closer to your mic"
            )

        elif cmd_key == "status":
            elapsed = int(time.monotonic() - self._session_start) if self._session_start else 0
            m, s = divmod(elapsed, 60)
            h, m = divmod(m, 60)
            if h:
                duration_str = f"{h}h {m:02d}m {s:02d}s"
            else:
                duration_str = f"{m}m {s:02d}s"
            self._slack_manager.post_message(
                team_id, channel_id,
                f"Recording duration: {duration_str} | Chunks: {self._chunk_count}"
            )

        elif cmd_key == "note":
            note_text = f"[NOTE: {remainder}]"
            self._chunk_texts.append(note_text)
            self._slack_manager.post_message(team_id, channel_id, note_text)

        elif cmd_key == "topic":
            topic_text = f"\n## {remainder}\n"
            self._chunk_texts.append(topic_text)
            self._slack_manager.post_message(team_id, channel_id, f"*Topic:* {remainder}")

        elif cmd_key == "help":
            self._slack_manager.post_message(team_id, channel_id, WELCOME_MESSAGE)

        elif cmd_key == "start recording":
            logger.warning("'start recording' command received but session already active — ignoring")

        else:
            logger.warning("Unknown command: %s", cmd_key)

    def _call_llm_summary(self, transcript: str, config: dict) -> str:
        """Worker thread: call Groq LLM to summarize the transcript."""
        try:
            from groq import Groq
            client = Groq(api_key=config.get("groq_api_key", ""), max_retries=0)
            resp = client.chat.completions.create(
                model=config.get("conv_groq_model", "meta-llama/llama-4-scout-17b-16e-instruct"),
                messages=[
                    {"role": "system", "content": "Summarize the following meeting transcript concisely."},
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
            from groq import Groq
            client = Groq(api_key=config.get("groq_api_key", ""), max_retries=0)
            resp = client.chat.completions.create(
                model=config.get("conv_groq_model", "meta-llama/llama-4-scout-17b-16e-instruct"),
                messages=[
                    {"role": "system", "content": "Extract action items from this meeting transcript. List each as a bullet point with owner if identifiable."},
                    {"role": "user", "content": transcript},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.error("LLM action items failed: %s", exc)
            return ""

    def _post_welcome(self, team_id: str, channel_id: str) -> None:
        """Worker thread: post welcome message to Slack channel."""
        self._slack_manager.post_message(team_id, channel_id, WELCOME_MESSAGE)

    def _post_confidence_alert(self, team_id: str, channel_id: str) -> None:
        """Worker thread: post low-confidence alert."""
        self._slack_manager.post_message(
            team_id, channel_id,
            "Having trouble understanding \u2014 please try speaking one at a time"
        )
        send_notification(
            "Low transcription confidence in huddle",
            body="Check Slack for alert"
        )

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

    def _finish_session(self) -> None:
        """GTK main thread: assemble final transcript and fire on_session_complete."""
        full_transcript = "\n".join(self._chunk_texts)
        elapsed = int(time.monotonic() - self._session_start) if self._session_start else 0
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        duration_str = f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"

        metadata = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "duration": duration_str,
            "chunk_count": self._chunk_count,
            "session_type": "huddle",
            "team_id": self._active_team_id,
            "channel_id": self._active_channel_id,
        }

        if self._recorder:
            self._recorder.cleanup()
            self._recorder = None

        if self._on_session_complete:
            self._on_session_complete(full_transcript, metadata)
