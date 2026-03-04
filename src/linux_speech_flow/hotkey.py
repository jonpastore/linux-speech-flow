import logging

from pynput import keyboard
from gi.repository import GLib

from linux_speech_flow.config import load_config
from linux_speech_flow.recorder import AudioRecorder
from linux_speech_flow.sounds import play_sound
from linux_speech_flow.notify import send_notification

logger = logging.getLogger(__name__)


_MODIFIER_NAMES = frozenset({'ctrl', 'alt', 'shift', 'super'})
_MODIFIER_ORDER = ['ctrl', 'alt', 'shift', 'super']

HOTKEY_DEFAULTS = {
    'record':       'ctrl+alt+r',
    'stop':         'ctrl+alt+r',
    'conversation': 'ctrl+alt+c',
    'reprocess':    'ctrl+alt+p',
    'feedback':     'ctrl+alt+f',
}

HOTKEY_CONFIG_KEYS = {
    'record':       'hotkey_record',
    'stop':         'hotkey_stop',
    'conversation': 'hotkey_conversation',
    'reprocess':    'hotkey_reprocess',
    'feedback':     'hotkey_feedback',
}

HOTKEY_ACTION_LABELS = {
    'record':       'Record Toggle',
    'stop':         'Stop Recording',
    'conversation': 'Conversation Mode',
    'reprocess':    'Reprocess Failed',
    'feedback':     'Feedback Toggle',
}

DANGEROUS_COMBOS = frozenset({
    'ctrl+alt+delete',
    'ctrl+alt+left', 'ctrl+alt+right',
    'ctrl+alt+f1',  'ctrl+alt+f2',  'ctrl+alt+f3',  'ctrl+alt+f4',
    'ctrl+alt+f5',  'ctrl+alt+f6',  'ctrl+alt+f7',  'ctrl+alt+f8',
    'ctrl+alt+f9',  'ctrl+alt+f10', 'ctrl+alt+f11', 'ctrl+alt+f12',
})


def parse_combo(combo_str: str) -> tuple[frozenset, str]:
    """Parse 'ctrl+alt+r' -> (frozenset({'ctrl', 'alt'}), 'r').

    Returns (frozenset(), '') for malformed input.
    """
    parts = combo_str.lower().split('+')
    modifiers = frozenset(p for p in parts if p in _MODIFIER_NAMES)
    key_parts = [p for p in parts if p not in _MODIFIER_NAMES]
    key_id = key_parts[0] if key_parts else ''
    return modifiers, key_id


def combo_display(combo_str: str) -> str:
    """'ctrl+alt+r' -> 'Ctrl+Alt+R' (canonical display string)."""
    _DISPLAY = {'ctrl': 'Ctrl', 'alt': 'Alt', 'shift': 'Shift', 'super': 'Super'}
    parts = combo_str.lower().split('+')
    result = []
    for m in _MODIFIER_ORDER:
        if m in parts:
            result.append(_DISPLAY[m])
    for p in parts:
        if p not in _MODIFIER_NAMES:
            result.append(p.upper() if len(p) == 1 else p.capitalize())
    return '+'.join(result)


class HotkeyManager:
    """Hotkey manager for recording and conversation mode.

    Bindings are loaded from config (hotkey_record, hotkey_stop, hotkey_conversation,
    hotkey_reprocess, hotkey_feedback) and can be reloaded at runtime via reload_bindings().

    Default bindings:
      Ctrl+Alt+R  — start / stop recording
      Ctrl+Alt+R  — stop recording (same default as record toggle)
      Ctrl+Alt+C  — start / stop conversation mode
      Ctrl+Alt+P  — reprocess failed recordings
      Ctrl+Alt+F  — toggle feedback mode (conversation only)
      ESC         — stop recording (hardcoded, not configurable)

    Threading contract:
    - pynput Listener callbacks fire from the Listener daemon thread.
      They must NOT call GTK/GLib functions directly.
    - All GTK operations are dispatched via GLib.idle_add() to run on
      the GTK main thread.
    - AudioRecorder callbacks already arrive on the GTK main thread via
      GLib.idle_add in recorder.py.
    - _bindings is read from the pynput thread (_on_press/_matches_binding)
      but written only from the GTK main thread via reload_bindings() or
      apply_binding_override(). No lock is used; the GIL and GTK single-thread
      rule provide sufficient ordering for this read-mostly dict.
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
        self._modifiers_held: set[str] = set()
        self._bindings: dict[str, tuple[frozenset, str]] = {}
        self._MODIFIER_MAP = {
            keyboard.Key.ctrl:    'ctrl', keyboard.Key.ctrl_l:  'ctrl', keyboard.Key.ctrl_r:  'ctrl',
            keyboard.Key.alt:     'alt',  keyboard.Key.alt_l:   'alt',  keyboard.Key.alt_r:   'alt',
            keyboard.Key.alt_gr:  'alt',
            keyboard.Key.shift:   'shift', keyboard.Key.shift_l: 'shift', keyboard.Key.shift_r: 'shift',
            keyboard.Key.cmd:     'super', keyboard.Key.cmd_r:   'super',
        }
        self._reload_bindings_from_config()

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

    def reload_bindings(self) -> None:
        """Hot-reload bindings from config. Safe to call from GTK main thread."""
        self._reload_bindings_from_config()

    def apply_binding_override(self, action: str, combo_str: str) -> None:
        """Apply a single binding immediately without requiring a config save."""
        self._bindings[action] = parse_combo(combo_str)

    def _reload_bindings_from_config(self) -> None:
        config = load_config()
        self._bindings = {
            action: parse_combo(config.get(HOTKEY_CONFIG_KEYS[action], HOTKEY_DEFAULTS[action]))
            for action in HOTKEY_DEFAULTS
        }

    def _matches_binding(self, key, action: str) -> bool:
        binding = self._bindings.get(action)
        if binding is None:
            return False
        mods, key_id = binding
        if self._modifiers_held != mods:
            return False
        if len(key_id) == 1:
            return self._key_letter(key) == key_id
        try:
            return key == keyboard.Key[key_id]
        except KeyError:
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
        if key in self._MODIFIER_MAP:
            self._modifiers_held.add(self._MODIFIER_MAP[key])
            return

        if not self._started:
            return

        if key == keyboard.Key.esc and self._state == self._STATE_RECORDING:
            GLib.idle_add(self._stop_recording, False)
            return

        if self._matches_binding(key, 'record'):
            if self._state == self._STATE_IDLE:
                GLib.idle_add(self._start_recording)
            elif self._state == self._STATE_RECORDING:
                GLib.idle_add(self._stop_recording_hotkey)
        elif self._matches_binding(key, 'stop') and self._state == self._STATE_RECORDING:
            GLib.idle_add(self._stop_recording, False)
        elif self._matches_binding(key, 'conversation'):
            if self._state == self._STATE_IDLE:
                GLib.idle_add(self._conv_start)
            elif self._state == self._STATE_CONVERSATION:
                GLib.idle_add(self._conv_stop)
        elif self._matches_binding(key, 'reprocess'):
            GLib.idle_add(self._on_reprocess)
        elif self._matches_binding(key, 'feedback') and self._state == self._STATE_CONVERSATION:
            GLib.idle_add(self._conv_feedback_toggle)

    def _on_release(self, key):
        if key in self._MODIFIER_MAP:
            self._modifiers_held.discard(self._MODIFIER_MAP[key])

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
