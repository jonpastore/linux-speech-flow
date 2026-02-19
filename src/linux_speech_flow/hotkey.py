import logging

from pynput import keyboard
from gi.repository import GLib

from linux_speech_flow.config import load_config
from linux_speech_flow.recorder import AudioRecorder
from linux_speech_flow.sounds import play_sound
from linux_speech_flow.notify import send_notification

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Toggle-mode recording hotkey: F9 starts, ESC stops.

    Threading contract:
    - pynput Listener callbacks (_on_press) fire from the Listener
      daemon thread. They must NOT call GTK/GLib functions directly.
    - All GTK operations (_start_recording, _stop_recording, etc.) are
      dispatched via GLib.idle_add() to run on the GTK main thread.
    - AudioRecorder callbacks (on_complete, on_error) already arrive on the
      GTK main thread via GLib.idle_add in recorder.py.
    """

    _STATE_IDLE = "idle"
    _STATE_RECORDING = "recording"

    def __init__(self, on_recording_complete, on_recording_start=None, on_recording_error=None, on_reprocess=None):
        """
        Args:
            on_recording_complete: Callable(wav_path: str) — called on GTK main
                thread when recording finishes normally. wav_path is ready for
                Phase 3 transcription. May be None for Phase 2 standalone testing.
            on_recording_start: Optional callable() — called on GTK main thread
                immediately when recording starts (tray state update).
            on_recording_error: Optional callable(message: str) — called on GTK
                main thread on mic error. If None, errors are shown but not propagated.
            on_reprocess: Optional callable() — called on GTK main thread when F10
                is pressed to reprocess failed recordings.
        """
        self._on_complete_cb = on_recording_complete
        self._on_recording_start_cb = on_recording_start
        self._on_error_cb = on_recording_error
        self._on_reprocess_cb = on_reprocess
        self._state = self._STATE_IDLE
        self._recorder: AudioRecorder | None = None
        self._notif_id: int | None = None
        self._started = False

        self._stop_was_f9 = False  # tracks which key ended the last recording

        self._listener = keyboard.Listener(
            on_press=self._on_press,
        )
        self._listener.daemon = True

    def start(self) -> None:
        """Start the global keyboard listener. Call from do_startup()."""
        self._listener.start()

    def stop(self) -> None:
        """Stop the listener and cancel any in-progress recording."""
        if self._recorder:
            self._recorder.stop(cancel=True)
            self._recorder = None
        self._listener.stop()

    def mark_started(self) -> bool:
        """Called via GLib.idle_add after first GTK main loop tick.
        Guards against F9 being held when the app starts.
        Returns False so GLib.idle_add removes this callback.
        """
        self._started = True
        return False

    def _on_press(self, key):
        if not self._started:
            return
        if key == keyboard.Key.f9 and self._state == self._STATE_IDLE:
            GLib.idle_add(self._start_recording)
        elif key == keyboard.Key.f9 and self._state == self._STATE_RECORDING:
            GLib.idle_add(self._stop_recording_f9)
        elif key == keyboard.Key.esc and self._state == self._STATE_RECORDING:
            GLib.idle_add(self._stop_recording, False)
        elif key == keyboard.Key.f10:
            GLib.idle_add(self._on_f10)

    def _on_f10(self) -> bool:
        if self._on_reprocess_cb:
            self._on_reprocess_cb()
        return False

    def _start_recording(self) -> bool:
        """Start audio capture. Called on GTK main thread."""
        if self._state != self._STATE_IDLE:
            return False
        self._state = self._STATE_RECORDING
        if self._on_recording_start_cb:
            self._on_recording_start_cb()
        self._stop_was_f9 = False  # reset for new recording

        config = load_config()
        sounds_enabled = config.get("sounds_enabled", True)
        output_device = config.get("sounds_output_device", "")
        device_name = config.get("microphone", "")
        max_dur = config.get("max_recording_duration", 300)
        silence_dur = config.get("silence_stop_duration", 10)

        logger.info("start recording sounds_enabled=%s device=%r", sounds_enabled, output_device)
        play_sound("start.wav", output_device=output_device, enabled=sounds_enabled)
        self._notif_id = send_notification("Recording...")

        self._recorder = AudioRecorder(
            device_name=device_name,
            max_duration=max_dur,
            silence_duration=silence_dur,
        )
        self._recorder.start(
            on_complete=self._on_recorder_complete,
            on_error=self._on_recorder_error,
        )
        return False

    def _stop_recording_f9(self) -> bool:
        """Stop recording when F9 is the stop key. Sets _stop_was_f9=True on the
        GTK thread (not pynput thread) to avoid race with silence auto-stop."""
        self._stop_was_f9 = True
        return self._stop_recording(False)

    def _stop_recording(self, cancel: bool) -> bool:
        """Stop or cancel an in-progress recording. Called on GTK main thread."""
        if self._state != self._STATE_RECORDING:
            return False
        if self._recorder:
            self._recorder.stop(cancel=cancel)
            self._recorder = None

        if cancel:
            config = load_config()
            sounds_enabled = config.get("sounds_enabled", True)
            output_device = config.get("sounds_output_device", "")
            play_sound("stop.wav", output_device=output_device, enabled=sounds_enabled)
            self._state = self._STATE_IDLE

        # Normal stop: don't play chime here — _on_recorder_complete handles it
        # for both manual ESC stop and auto-stop paths (silence, max duration)
        return False

    def _on_recorder_complete(self, wav_path: str) -> bool:
        """Called on GTK main thread by AudioRecorder when WAV is ready.

        This fires for ALL normal completion paths: silence auto-stop and
        max-duration auto-stop. Per CONTEXT.md Area 2, normal stop always
        plays the descending stop chime. Load config here the same way
        _stop_recording does so sounds_enabled and sounds_output_device are
        respected on auto-stop paths too.
        """
        config = load_config()
        sounds_enabled = config.get("sounds_enabled", True)
        output_device = config.get("sounds_output_device", "")
        play_sound("stop.wav", output_device=output_device, enabled=sounds_enabled)

        self._state = self._STATE_IDLE
        if self._on_complete_cb:
            self._on_complete_cb(wav_path, self._stop_was_f9)
        return False

    def _on_recorder_error(self, message: str) -> bool:
        """Called on GTK main thread by AudioRecorder on mic error."""
        self._state = self._STATE_IDLE
        self._recorder = None

        config = load_config()
        sounds_enabled = config.get("sounds_enabled", True)
        output_device = config.get("sounds_output_device", "")
        play_sound("error.wav", output_device=output_device, enabled=sounds_enabled)
        send_notification(
            "Microphone unavailable — check Settings",
            body=message,
        )
        if self._on_error_cb:
            self._on_error_cb(message)
        return False
