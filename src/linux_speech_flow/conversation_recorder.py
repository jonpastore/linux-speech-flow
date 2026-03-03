import logging
import math
import os
import pasimple
import shutil
import struct
import tempfile
import threading
import wave

from gi.repository import GLib

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
CHUNK_DURATION = 0.1            # seconds per read() call
CHUNK_BYTES = int(SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * CHUNK_DURATION)
MIN_GUARD_FRAMES = 10           # ignore silence detection for first N frames (PulseAudio buffer fill)
RMS_DISPLAY_SCALE = 12          # multiplier so typical speech reaches ~0.5–1.0 on a 0–1 LevelBar
CALIB_FACTOR = 4.0          # threshold = ambient_rms * CALIB_FACTOR
CALIB_MIN = 0.002           # floor: never go below this
CALIB_MAX = 0.030           # ceiling: noisy environments


class ConversationRecorder:
    """Long-form chunked recorder for Conversation Mode.

    Records continuously from a PulseAudio/PipeWire source. Detects silence
    to segment the audio into speech chunks. Each completed chunk (a WAV file)
    is delivered to on_chunk_ready(wav_path: str) on the GTK main thread.

    Chunks are written to a temp directory (lsf-conv-XXXX). Call cleanup()
    after all chunk WAVs have been consumed to remove the directory.

    Threading model:
    - start() called from GTK main thread.
    - _record_loop() runs in a daemon thread; never touches GTK directly.
    - on_chunk_ready and on_error dispatched via GLib.idle_add (GTK main thread).
    - stop() is safe from any thread (sets a threading.Event).
    """

    def __init__(
        self,
        device_name: str | None,
        chunk_silence_sec: int = 3,
        silence_rms_threshold: float = 0.005,
    ):
        self._device_name = device_name or None
        self._chunk_silence_sec = chunk_silence_sec
        self._silence_rms_threshold = silence_rms_threshold
        self._stop_event = threading.Event()
        self._chunk_dir = tempfile.mkdtemp(prefix="lsf-conv-")
        self._on_chunk_ready = None
        self._on_error = None
        self._on_silence_tick = None
        self._on_audio_level = None
        self._on_threshold_calibrated = None

    def start(self, on_chunk_ready, on_error, on_silence_tick=None, on_audio_level=None, on_threshold_calibrated=None) -> None:
        """Start recording in a daemon thread.

        Args:
            on_chunk_ready: Callable(wav_path: str) — GTK main thread; wav_path
                is an existing WAV file in the temp dir, ready for transcription.
                Called once per completed chunk. Caller is responsible for
                consuming (reading and deleting) the chunk.
            on_error: Callable(message: str) — GTK main thread; called on
                PaSimpleError or any recording failure. Recording stops.
            on_silence_tick: Callable(silence_frames: int) — GTK main thread via
                GLib.idle_add; silence_frames is the current consecutive silent
                frame count within the current chunk (0 = voice detected); emitted
                only when value changes (debounced).
            on_audio_level: Callable(level: float) — GTK main thread via
                GLib.idle_add; level is RMS * RMS_DISPLAY_SCALE clamped to 1.0,
                emitted every frame after the guard period for live level display.
        """
        self._on_chunk_ready = on_chunk_ready
        self._on_error = on_error
        self._on_silence_tick = on_silence_tick
        self._on_audio_level = on_audio_level
        self._on_threshold_calibrated = on_threshold_calibrated
        self._stop_event.clear()
        threading.Thread(target=self._record_loop, daemon=True).start()

    def set_threshold(self, value: float) -> None:
        """Update silence RMS threshold live. Safe to call from any thread."""
        self._silence_rms_threshold = value

    def stop(self) -> None:
        """Signal the recording thread to finalise the current chunk and stop.
        Safe to call from any thread. The last incomplete chunk is emitted
        if it contains any recorded audio.
        """
        self._stop_event.set()

    def cleanup(self) -> None:
        """Remove the temporary chunk directory and all files in it.
        Call only after all chunks have been consumed (or after stop()).
        """
        shutil.rmtree(self._chunk_dir, ignore_errors=True)

    def _record_loop(self) -> None:
        silence_limit_frames = int(self._chunk_silence_sec / CHUNK_DURATION)
        chunk_index = 0
        logger.info(
            "record_loop: start device=%r chunk_silence_frames=%d (%.1fs) rms_threshold=%.4f",
            self._device_name or "default", silence_limit_frames, self._chunk_silence_sec,
            self._silence_rms_threshold,
        )

        try:
            with pasimple.PaSimple(
                pasimple.PA_STREAM_RECORD,
                pasimple.PA_SAMPLE_S16LE,
                CHANNELS,
                SAMPLE_RATE,
                app_name="linux-speech-flow",
                stream_name="conv-recording",
                device_name=self._device_name,
            ) as pa:
                while not self._stop_event.is_set():
                    chunk_path = os.path.join(
                        self._chunk_dir, f"chunk_{chunk_index:04d}.wav"
                    )
                    frames_written, had_audio = self._record_one_chunk(
                        pa, chunk_path, silence_limit_frames, chunk_index,
                    )
                    if frames_written > 0 and had_audio:
                        logger.info(
                            "record_loop: chunk %d complete (audio) frames=%d — dispatching",
                            chunk_index, frames_written,
                        )
                        chunk_index += 1
                        GLib.idle_add(self._on_chunk_ready, chunk_path)
                    elif frames_written > 0:
                        logger.info(
                            "record_loop: chunk %d complete (silence-only) frames=%d — discarding",
                            chunk_index, frames_written,
                        )
                        # Pure silence chunk (e.g. noise floor at start); discard
                        try:
                            os.unlink(chunk_path)
                        except OSError:
                            pass

        except pasimple.PaSimpleError as exc:
            logger.error("record_loop: PaSimpleError: %s", exc)
            GLib.idle_add(self._on_error, str(exc))

        logger.info("record_loop: exit — stop_event was set")

    def _record_one_chunk(self, pa, wav_path: str, silence_limit_frames: int, chunk_index: int = 0):
        """Record until a silence boundary or stop_event is set.

        Returns (frames_written: int, had_audio: bool).
        had_audio is True if at least one non-silent frame was recorded
        (used to discard leading-silence chunks).
        """
        silence_frames = 0
        frames_written = 0
        had_audio = False
        last_emitted_silence = -1
        LOG_SILENCE_EVERY = 100
        last_logged_frame = 0

        # Auto-calibration: measure ambient noise during guard period of first chunk only
        calib_rms_sum = 0.0
        calib_done = (chunk_index != 0)

        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)

            while not self._stop_event.is_set():
                raw = pa.read(CHUNK_BYTES)
                wf.writeframes(raw)
                frames_written += 1

                # Unpack samples once per frame for RMS
                samples = struct.unpack(f"{len(raw) // SAMPLE_WIDTH}h", raw)
                rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0

                # Auto-calibration: accumulate ambient RMS during guard period
                if not calib_done:
                    if frames_written < MIN_GUARD_FRAMES:
                        calib_rms_sum += rms
                    elif frames_written == MIN_GUARD_FRAMES:
                        n = MIN_GUARD_FRAMES - 1
                        if n > 0:
                            ambient = calib_rms_sum / n
                            if ambient >= self._silence_rms_threshold:
                                # Guard frames contain audio above threshold — user was
                                # already speaking; calibration would set a false ceiling.
                                # Keep the current (more sensitive) threshold instead.
                                logger.info(
                                    "auto_calibrate: skipped — ambient_rms=%.5f >= threshold=%.5f"
                                    " (user likely speaking during guard)",
                                    ambient, self._silence_rms_threshold,
                                )
                            else:
                                calibrated = max(CALIB_MIN, min(CALIB_MAX, ambient * CALIB_FACTOR))
                                logger.info(
                                    "auto_calibrate: ambient_rms=%.5f -> threshold=%.5f (%.1fx)",
                                    ambient, calibrated, CALIB_FACTOR,
                                )
                                self._silence_rms_threshold = calibrated
                                if self._on_threshold_calibrated:
                                    GLib.idle_add(self._on_threshold_calibrated, calibrated)
                        calib_done = True

                if frames_written >= MIN_GUARD_FRAMES:
                    if rms < self._silence_rms_threshold:
                        silence_frames += 1
                    else:
                        silence_frames = 0
                        had_audio = True

                    if self._on_audio_level:
                        GLib.idle_add(self._on_audio_level, min(1.0, rms * RMS_DISPLAY_SCALE))

                    if self._on_silence_tick and silence_frames != last_emitted_silence:
                        last_emitted_silence = silence_frames
                        GLib.idle_add(self._on_silence_tick, silence_frames)

                    if frames_written - last_logged_frame >= LOG_SILENCE_EVERY:
                        last_logged_frame = frames_written
                        logger.debug(
                            "chunk %d: frame=%d silence_frames=%d/%.0f had_audio=%s rms=%.4f threshold=%.4f",
                            chunk_index, frames_written, silence_frames, silence_limit_frames,
                            had_audio, rms, self._silence_rms_threshold,
                        )

                    if silence_frames >= silence_limit_frames:
                        logger.info(
                            "chunk %d: silence boundary reached at frame=%d "
                            "(%.1fs silence) had_audio=%s",
                            chunk_index, frames_written,
                            silence_frames * CHUNK_DURATION, had_audio,
                        )
                        break

        if self._stop_event.is_set():
            logger.info(
                "chunk %d: stopped by stop_event at frame=%d had_audio=%s",
                chunk_index, frames_written, had_audio,
            )

        return frames_written, had_audio
