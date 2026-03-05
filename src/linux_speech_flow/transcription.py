import logging
import os
import queue
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import groq
from gi.repository import GLib

from linux_speech_flow.config import load_config
from linux_speech_flow.history import HistoryStore
from linux_speech_flow.injector import paste_text
from linux_speech_flow.notify import send_notification
from linux_speech_flow.sounds import play_sound
from linux_speech_flow.window_context import get_active_window_info

logger = logging.getLogger(__name__)

FIBONACCI_DELAYS = [5, 8, 13, 21, 34]
FAILED_DIR = Path.home() / ".local" / "share" / "linux-speech-flow" / "failed"
MIN_TRANSCRIPT_LEN = 3

_WHISPER_HALLUCINATIONS = {
    "thank you",
    "thank you.",
    "thanks for watching",
    "thanks for watching.",
    "thank you for watching",
    "thank you for watching.",
    "thank you for watching!",
    "please subscribe",
    "please subscribe.",
    "like and subscribe",
    "like and subscribe.",
    "subscribe",
    "subscribe.",
}


def _strip_hallucinations(text: str) -> str:
    lines = text.splitlines()
    while lines and lines[-1].strip().lower() in _WHISPER_HALLUCINATIONS:
        logger.debug("stripped Whisper hallucination: %r", lines[-1])
        lines.pop()
    return "\n".join(lines).strip()


def _failed_wav_name() -> str:
    return f"recording_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:4]}.wav"


def _call_with_retry(fn, *args, retryable, **kwargs):
    """Call fn(*args, **kwargs), retrying on retryable exceptions with Fibonacci backoff.
    Raises the last exception after all delays are exhausted.
    """
    last_exc = None
    for delay in FIBONACCI_DELAYS:
        try:
            return fn(*args, **kwargs)
        except retryable as exc:
            last_exc = exc
            time.sleep(delay)
    raise last_exc


def _classify_groq_error(exc: groq.APIError) -> str:
    if isinstance(exc, groq.AuthenticationError):
        return "Invalid API key — check Settings"
    if isinstance(exc, groq.RateLimitError):
        return "Rate limit exceeded — try again shortly"
    if isinstance(exc, groq.APIConnectionError):
        return "Network error — check your internet connection"
    return f"Groq API error: {getattr(exc, 'status_code', 'unknown')}"


def _build_user_message(
    raw_transcript: str, window_info: dict, vocabulary: list
) -> str:
    parts = []
    if window_info.get("wm_class") or window_info.get("title"):
        parts.append(
            f"<context>\n"
            f"Application: {window_info.get('wm_class', '')}\n"
            f"Window title: {window_info.get('title', '')}\n"
            f"App category: {window_info.get('category', 'other')}\n"
            f"</context>\n"
        )
    if vocabulary:
        vocab_str = "\n".join(f"- {word}" for word in vocabulary)
        parts.append(
            f"<vocabulary>\n"
            f"The following words or phrases are correct and must not be altered:\n"
            f"{vocab_str}\n"
            f"</vocabulary>\n"
        )
    parts.append(f"Transcript:\n{raw_transcript}")
    return "\n".join(parts)


class TranscriptionPipeline:
    """Background pipeline: WAV -> Whisper -> LLM -> clipboard paste.

    Threading contract:
    - submit() is called from the GTK main thread; it captures window context
      immediately (before API calls) to prevent focus-theft by notifications.
    - _run() runs on a daemon worker thread; all GTK side-effects go via GLib.idle_add().
    - One worker thread processes the queue serially (FIFO). F9 presses during
      active pipeline add to the queue; the caller shows a "Recording queued" notification.
    """

    def __init__(
        self,
        on_paste_complete=None,
        on_error=None,
        on_failed_count_changed=None,
        history_store=None,
        on_history_entry=None,
    ):
        self._queue: queue.Queue = queue.Queue()
        self._on_paste_complete = on_paste_complete
        self._on_error = on_error
        self._on_failed_count_changed = on_failed_count_changed
        self._history_store = history_store
        self._on_history_entry = on_history_entry
        self._worker = threading.Thread(
            target=self._run, daemon=True, name="transcription-worker"
        )
        self._worker.start()

    def _get_failed_count(self) -> int:
        return len(list(FAILED_DIR.glob("*.wav"))) if FAILED_DIR.exists() else 0

    def _notify_failed_count(self):
        if self._on_failed_count_changed:
            count = self._get_failed_count()
            GLib.idle_add(self._on_failed_count_changed, count)

    def submit(self, wav_path: str, stop_was_hotkey: bool = False) -> int:
        """Queue wav_path for processing. Returns queue depth AFTER insert.

        Captures window context NOW (on GTK main thread) to avoid focus-theft
        by notifications fired during API calls. Returns depth so caller can
        notify user if depth > 1 ("Recording queued (N pending)").

        stop_was_hotkey: True when the record-stop hotkey ended recording.
        Ctrl+Alt combos do not produce literal text in target windows on X11,
        so leaked_hotkey_count is always 0 regardless.
        """
        config = load_config()
        app_categories = config.get("app_categories", {})
        window_info = get_active_window_info(app_categories=app_categories)
        # Ctrl+Alt+R hotkey does not produce literal text in target windows on X11.
        window_info["leaked_hotkey_count"] = 0
        logger.info(
            "submit wav=%s window_id=%s wm_class=%r category=%s session=%s",
            wav_path,
            window_info.get("window_id"),
            window_info.get("wm_class"),
            window_info.get("category"),
            window_info.get("session"),
        )
        self._queue.put((wav_path, window_info, config))
        return self._queue.qsize()

    def submit_batch_to_file(self, wav_paths: list[str]) -> str:
        """Submit multiple WAVs for batch reprocess to a text file.

        Returns the output file path. Each WAV is transcribed and post-processed
        in FIFO order; results are written to a temp file which is then opened
        in the default text editor via xdg-open.
        """
        import tempfile

        fd, output_path = tempfile.mkstemp(
            suffix=".txt", prefix="linux-speech-flow-batch-"
        )
        os.close(fd)
        for wav_path in wav_paths:
            config = load_config()
            app_categories = config.get("app_categories", {})
            window_info = get_active_window_info(app_categories=app_categories)
            window_info["batch_output_path"] = output_path
            self._queue.put((wav_path, window_info, config))
        return output_path

    def _run(self):
        while True:
            item = self._queue.get()
            try:
                self._process(*item)
            except Exception as exc:
                GLib.idle_add(self._dispatch_error, str(exc))
            finally:
                self._queue.task_done()

    def _process(self, wav_path: str, window_info: dict, config: dict):
        started_at = datetime.utcnow()
        api_key = config.get("groq_api_key", "")
        client = groq.Groq(api_key=api_key, max_retries=0)

        sounds_enabled = config.get("sounds_enabled", True)
        output_device = config.get("sounds_output_device", "")
        processing_enabled = config.get("processing_sound_enabled", True)
        success_enabled = config.get("success_sound_enabled", True)
        processing_sound_file = config.get("processing_sound_file", "") or None
        success_sound_file = config.get("success_sound_file", "") or None
        whisper_model = config.get("whisper_model", "whisper-large-v3-turbo")
        llm_model = config.get("llm_model", "meta-llama/llama-4-scout-17b-16e-instruct")
        system_prompt = config.get("llm_system_prompt", "")
        vocabulary = config.get("vocabulary", [])

        logger.info(
            "processing wav=%s whisper_model=%s llm_model=%s",
            wav_path,
            whisper_model,
            llm_model,
        )

        if sounds_enabled and processing_enabled:
            GLib.timeout_add(
                400,
                play_sound,
                "processing.wav",
                output_device,
                True,
                processing_sound_file,
            )

        retryable_errors = (groq.APIConnectionError, groq.RateLimitError)
        try:
            logger.info("calling Whisper API...")
            raw_transcript = _call_with_retry(
                self._transcribe,
                client,
                wav_path,
                whisper_model,
                retryable=retryable_errors,
            )
            logger.info(
                "transcript (%d chars): %r", len(raw_transcript), raw_transcript[:120]
            )
        except groq.AuthenticationError as exc:
            msg = _classify_groq_error(exc)
            logger.error("Whisper auth error: %s", msg)
            self._save_failed_wav(wav_path)
            GLib.idle_add(play_sound, "error.wav", output_device, sounds_enabled)
            GLib.idle_add(self._dispatch_api_error, msg, wav_path)
            return
        except Exception as exc:
            msg = (
                _classify_groq_error(exc)
                if isinstance(exc, groq.APIError)
                else str(exc)
            )
            logger.error("Whisper error: %s", msg)
            self._save_failed_wav(wav_path)
            GLib.idle_add(play_sound, "error.wav", output_device, sounds_enabled)
            GLib.idle_add(self._dispatch_api_error, msg, wav_path)
            return

        if len(raw_transcript.strip()) < MIN_TRANSCRIPT_LEN:
            logger.info(
                "transcript too short (%d chars) — skipping",
                len(raw_transcript.strip()),
            )
            try:
                os.unlink(wav_path)
            except OSError:
                pass
            GLib.idle_add(
                send_notification,
                "No speech detected",
                "Recording was too short or silent.",
            )
            return

        final_text = raw_transcript
        llm_failed = False
        try:
            logger.info("calling LLM post-process (model=%s)...", llm_model)
            user_message = _build_user_message(raw_transcript, window_info, vocabulary)
            final_text = _call_with_retry(
                self._postprocess,
                client,
                user_message,
                system_prompt,
                llm_model,
                retryable=retryable_errors,
            )
            logger.info("LLM result (%d chars): %r", len(final_text), final_text[:120])
        except Exception as exc:
            logger.warning(
                "LLM post-process failed (%s) — falling back to raw transcript", exc
            )
            llm_failed = True
            final_text = raw_transcript

        batch_path = window_info.get("batch_output_path")
        if batch_path:
            with open(batch_path, "a") as f:
                f.write(final_text + "\n\n")
            if self._queue.empty():
                import subprocess

                subprocess.Popen(["xdg-open", batch_path], stderr=subprocess.DEVNULL)
            try:
                os.unlink(wav_path)
            except OSError:
                pass
            self._notify_failed_count()
            return

        final_text = final_text + " "
        logger.info(
            "pasting %d chars to window_id=%s",
            len(final_text),
            window_info.get("window_id"),
        )
        paste_text(final_text, window_info)

        try:
            os.unlink(wav_path)
        except OSError:
            pass

        duration = (datetime.utcnow() - started_at).total_seconds()
        if self._history_store:
            max_entries = config.get("history_max_entries", 20)
            self._history_store.insert(
                {
                    "entry_type": "transcription",
                    "created_at": started_at.isoformat(),
                    "duration_sec": duration,
                    "raw_text": raw_transcript,
                    "processed_text": final_text.strip(),
                    "app_name": window_info.get("wm_class", ""),
                    "window_title": window_info.get("title", ""),
                },
                max_entries=max_entries,
            )
        if self._on_history_entry:
            GLib.idle_add(
                self._on_history_entry,
                {
                    "entry_type": "transcription",
                    "created_at": started_at.isoformat(),
                    "duration_sec": duration,
                    "raw_text": raw_transcript,
                    "processed_text": final_text.strip(),
                    "app_name": window_info.get("wm_class", ""),
                    "window_title": window_info.get("title", ""),
                },
            )

        self._notify_failed_count()

        if llm_failed:
            GLib.idle_add(send_notification, "LLM failed — raw transcript pasted", "")
        elif window_info.get("session") == "wayland":
            GLib.idle_add(
                send_notification, "Text copied to clipboard", "Press Ctrl+V to paste."
            )

        if sounds_enabled and success_enabled:
            GLib.idle_add(
                play_sound, "success.wav", output_device, True, success_sound_file
            )

        if self._on_paste_complete:
            GLib.idle_add(self._on_paste_complete)

    def _transcribe(self, client: groq.Groq, wav_path: str, model: str) -> str:
        with open(wav_path, "rb") as f:
            result = client.audio.transcriptions.create(
                file=f,
                model=model,
                response_format="text",
                language="en",
                temperature=0.0,
            )
        raw = result.strip() if isinstance(result, str) else str(result).strip()
        return _strip_hallucinations(raw)

    def _postprocess(
        self, client: groq.Groq, user_message: str, system_prompt: str, model: str
    ) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()

    def _save_failed_wav(self, wav_path: str) -> str | None:
        """Move WAV to failed/ directory. Returns new path or None on error."""
        try:
            FAILED_DIR.mkdir(parents=True, exist_ok=True)
            dest = FAILED_DIR / _failed_wav_name()
            shutil.move(wav_path, dest)
            logger.info("WAV saved to failed/: %s", dest)
            self._notify_failed_count()
            return str(dest)
        except Exception as exc:
            logger.error("failed to save WAV to failed/: %s", exc)
            return None

    def _dispatch_api_error(self, message: str, wav_path: str):
        logger.info("dispatching API error notification: %s", message)
        result = send_notification(
            "Transcription failed — Press Ctrl+Alt+P to reprocess", message
        )
        logger.info("notification sent, id=%s", result)
        if self._on_error:
            self._on_error(message)
        return False

    def _dispatch_error(self, message: str):
        send_notification("Pipeline error", message)
        if self._on_error:
            self._on_error(message)
        return False
