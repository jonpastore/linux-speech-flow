import math
import os
import struct
import tempfile
import threading
import wave

import pasimple

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
CHUNK_DURATION = 0.1
CHUNK_BYTES = int(SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * CHUNK_DURATION)
SILENCE_RMS_THRESHOLD = 0.005
MIN_SILENCE_GUARD_CHUNKS = 10


class AudioRecorder:
    """Records audio from a PulseAudio/PipeWire source to a temp WAV file.

    Threading model:
    - start() is called from the GTK main thread.
    - _record_loop() runs in a daemon thread (never touches GTK directly).
    - on_complete and on_error callbacks are dispatched via GLib.idle_add
      so they run on the GTK main thread.
    - stop(cancel=False) is safe to call from any thread.
    """

    def __init__(
        self, device_name: str | None, max_duration: int, silence_duration: int
    ):
        """
        Args:
            device_name: PulseAudio source name from config["microphone"].
                         None or empty string = PulseAudio default source.
            max_duration: Maximum recording seconds before auto-stop (produces WAV).
            silence_duration: Seconds of RMS silence before auto-stop (produces WAV).
        """
        self._device_name = device_name or None
        self._max_duration = max_duration
        self._silence_duration = silence_duration
        self._stop_event = threading.Event()
        self._cancel_flag = False
        self._wav_path: str | None = None
        self._thread: threading.Thread | None = None
        self._on_complete = None
        self._on_error = None

    def start(self, on_complete, on_error) -> None:
        """Start recording in a daemon thread.

        Args:
            on_complete: Callable(wav_path: str) — called on GTK main thread when
                         recording finishes normally (stop or auto-stop). wav_path
                         is the path to the completed WAV file in /tmp.
            on_error: Callable(message: str) — called on GTK main thread if
                      pasimple raises (mic unavailable or disconnected mid-record).
        """
        self._on_complete = on_complete
        self._on_error = on_error
        self._stop_event.clear()
        self._cancel_flag = False

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self._wav_path = tmp.name
        tmp.close()

        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop(self, cancel: bool = False) -> None:
        """Signal the recording thread to stop.

        Args:
            cancel: If True, discard the WAV file and do not call on_complete.
                    If False (normal stop), finalize WAV and call on_complete.
        Safe to call from any thread.
        """
        self._cancel_flag = cancel
        self._stop_event.set()

    def _record_loop(self) -> None:
        """Recording loop — runs entirely in daemon thread."""
        silence_limit = int(self._silence_duration / CHUNK_DURATION)
        max_chunks = int(self._max_duration / CHUNK_DURATION)
        silence_chunks = 0
        chunks_recorded = 0

        try:
            with (
                pasimple.PaSimple(
                    pasimple.PA_STREAM_RECORD,
                    pasimple.PA_SAMPLE_S16LE,
                    CHANNELS,
                    SAMPLE_RATE,
                    app_name="linux-speech-flow",
                    stream_name="recording",
                    device_name=self._device_name,
                ) as pa,
                wave.open(self._wav_path, "wb") as wf,
            ):
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(SAMPLE_WIDTH)
                wf.setframerate(SAMPLE_RATE)

                while not self._stop_event.is_set():
                    chunk = pa.read(CHUNK_BYTES)
                    wf.writeframes(chunk)
                    chunks_recorded += 1

                    if chunks_recorded >= MIN_SILENCE_GUARD_CHUNKS:
                        samples = struct.unpack(f"{len(chunk) // SAMPLE_WIDTH}h", chunk)
                        rms = (
                            math.sqrt(sum(s * s for s in samples) / len(samples))
                            / 32768.0
                        )
                        if rms < SILENCE_RMS_THRESHOLD:
                            silence_chunks += 1
                        else:
                            silence_chunks = 0
                        if silence_chunks >= silence_limit:
                            break

                    if chunks_recorded >= max_chunks:
                        break

                if self._stop_event.is_set() and not self._cancel_flag:
                    for _ in range(3):
                        wf.writeframes(pa.read(CHUNK_BYTES))

        except pasimple.PaSimpleError as exc:
            self._cleanup_wav()
            from gi.repository import GLib

            GLib.idle_add(self._on_error, str(exc))
            return

        if self._cancel_flag:
            self._cleanup_wav()
            return

        from gi.repository import GLib

        GLib.idle_add(self._on_complete, self._wav_path)

    def _cleanup_wav(self) -> None:
        """Delete the temp WAV file if it exists."""
        if self._wav_path and os.path.exists(self._wav_path):
            os.unlink(self._wav_path)
        self._wav_path = None
