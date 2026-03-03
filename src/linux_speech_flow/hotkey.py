import logging

from pynput import keyboard
from gi.repository import GLib

from linux_speech_flow.config import load_config
from linux_speech_flow.recorder import AudioRecorder
from linux_speech_flow.sounds import play_sound
from linux_speech_flow.notify import send_notification

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Hotkey manager for recording and conversation mode.

    Default bindings:
      Ctrl+Alt+R  — start / stop recording
      ESC         — stop recording
      Ctrl+Alt+C  — start / stop conversation mode
      Ctrl+Alt+P  — reprocess failed recordings
      Ctrl+Alt+F  — toggle feedback mode (conversation only)

    Threading contract:
    - pynput Listener callbacks fire from the Listener daemon thread.
      They must NOT call GTK/GLib functions directly.
    - All GTK operations are dispatched via GLib.idle_add() to run on
      the GTK main thread.
    - AudioRecorder callbacks already arrive on the GTK main thread via
      GLib.idle_add in recorder.py.
    """

    _STATE_IDLE = "idle"
    _STATE_RECORDING = "recording"
    _STATE_CONVERSATION = "conversation"

    def __init__(self, on_recording_complete, on_recording_start=None,
                 on_recording_error=None, on_reprocess=None,
                 on_conversation_start=None, on_conversation_stop=None,
                 on_conversation_feedback_toggle=None):
        self._on_complete_cb = on_recording_complete
        self._on_recording_start_cb = on_recording_start
        self._on_error_cb = on_recording_error
        self._on_reprocess_cb = on_reprocess
        self._on_conv_start_cb = on_conversation_start
        self._on_conv_stop_cb = on_conversation_stop
        self._on_conv_feedback_cb = on_conversation_feedback_toggle
        self._state = self._STATE_IDLE
        self._recorder: AudioRecorder | None = None
        self._notif_id: int | None = None
        self._started = False

        self._stop_was_hotkey = False  # True when record-stop hotkey ended recording
        self._ctrl_held = False
        self._alt_held = False

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        if self._recorder:
            self._recorder.stop(cancel=True)
            self._recorder = None
        self._listener.stop()

    def mark_started(self) -> bool:
        self._started = True
        return False

    @staticmethod
    def _key_letter(key) -> str | None:
        """Return the lowercase base letter for a key regardless of modifiers.

        Checks vk (X11 keysym = ASCII for Latin letters) first, then
        key.char for environments where vk is not available.
        """
        vk = getattr(key, 'vk', None)
        if vk is not None:
            if 65 <= vk <= 90:   # A-Z keysyms
                return chr(vk + 32)
            if 97 <= vk <= 122:  # a-z keysyms
                return chr(vk)
        char = getattr(key, 'char', None)
        if char and len(char) == 1 and char.isalpha():
            return char.lower()
        return None

    def _on_press(self, key):
        # Track modifier state (runs even before _started)
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self._ctrl_held = True
            return
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            self._alt_held = True
            return

        if not self._started:
            return

        ctrl_alt = self._ctrl_held and self._alt_held
        letter = self._key_letter(key)

        if ctrl_alt and letter == 'r':
            if self._state == self._STATE_IDLE:
                GLib.idle_add(self._start_recording)
            elif self._state == self._STATE_RECORDING:
                GLib.idle_add(self._stop_recording_hotkey)
        elif key == keyboard.Key.esc and self._state == self._STATE_RECORDING:
            GLib.idle_add(self._stop_recording, False)
        elif ctrl_alt and letter == 'c':
            if self._state == self._STATE_IDLE:
                GLib.idle_add(self._conv_start)
            elif self._state == self._STATE_CONVERSATION:
                GLib.idle_add(self._conv_stop)
        elif ctrl_alt and letter == 'p':
            GLib.idle_add(self._on_reprocess)
        elif ctrl_alt and letter == 'f' and self._state == self._STATE_CONVERSATION:
            GLib.idle_add(self._conv_feedback_toggle)

    def _on_release(self, key):
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self._ctrl_held = False
        elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            self._alt_held = False

    def _on_reprocess(self) -> bool:
        if self._on_reprocess_cb:
            self._on_reprocess_cb()
        return False

    def _start_recording(self) -> bool:
        if self._state != self._STATE_IDLE:
            return False
        self._state = self._STATE_RECORDING
        if self._on_recording_start_cb:
            self._on_recording_start_cb()
        self._stop_was_hotkey = False

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

    def _stop_recording_hotkey(self) -> bool:
        """Stop recording via the record hotkey (Ctrl+Alt+R)."""
        self._stop_was_hotkey = True
        return self._stop_recording(False)

    def _stop_recording(self, cancel: bool) -> bool:
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

        return False

    def _on_recorder_complete(self, wav_path: str) -> bool:
        config = load_config()
        sounds_enabled = config.get("sounds_enabled", True)
        output_device = config.get("sounds_output_device", "")
        play_sound("stop.wav", output_device=output_device, enabled=sounds_enabled)

        self._state = self._STATE_IDLE
        if self._on_complete_cb:
            self._on_complete_cb(wav_path, self._stop_was_hotkey)
        return False

    def _conv_start(self) -> bool:
        if self._state != self._STATE_IDLE:
            return False
        self._state = self._STATE_CONVERSATION
        try:
            if self._on_conv_start_cb:
                self._on_conv_start_cb()
        except Exception:
            logger.exception("_conv_start callback raised — resetting state to IDLE")
            self._state = self._STATE_IDLE
        return False

    def _conv_stop(self) -> bool:
        if self._state != self._STATE_CONVERSATION:
            return False
        self._state = self._STATE_IDLE
        try:
            if self._on_conv_stop_cb:
                self._on_conv_stop_cb()
        except Exception:
            logger.exception("_conv_stop callback raised")
        return False

    def _conv_feedback_toggle(self) -> bool:
        if self._on_conv_feedback_cb:
            self._on_conv_feedback_cb()
        return False

    def _on_recorder_error(self, message: str) -> bool:
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
