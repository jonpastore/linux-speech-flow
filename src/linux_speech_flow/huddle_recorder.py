import atexit
import logging
import subprocess

import pulsectl

from linux_speech_flow.conversation_recorder import ConversationRecorder

logger = logging.getLogger(__name__)
_MIX_SINK_NAME = "lsf-huddle-mix"
_MIX_MONITOR = f"{_MIX_SINK_NAME}.monitor"


def _emergency_cleanup() -> None:
    """atexit handler: unload any leftover lsf-huddle-mix modules on exit or crash."""
    try:
        with pulsectl.Pulse("lsf-atexit-cleanup") as pulse:
            for sink in pulse.sink_list():
                if sink.name == _MIX_SINK_NAME:
                    subprocess.run(
                        ["pactl", "unload-module", str(sink.owner_module)],
                        capture_output=True,
                    )
                    break
            for src in pulse.source_list():
                if _MIX_SINK_NAME in src.name:
                    for mod in pulse.module_list():
                        if "loopback" in (mod.name or "") and _MIX_SINK_NAME in (
                            mod.argument or ""
                        ):
                            subprocess.run(
                                ["pactl", "unload-module", str(mod.index)],
                                capture_output=True,
                            )
    except Exception:
        pass


atexit.register(_emergency_cleanup)


def get_default_monitor_source() -> str:
    """Return the monitor source name for the default output sink."""
    with pulsectl.Pulse("lsf-monitor-lookup") as pulse:
        return pulse.server_info().default_sink_name + ".monitor"


def _existing_sink_module_id(sink_name: str) -> str | None:
    """Return the owner-module id string if sink exists, else None."""
    try:
        with pulsectl.Pulse("lsf-sink-check") as pulse:
            for s in pulse.sink_list():
                if s.name == sink_name:
                    return str(s.owner_module)
    except Exception:
        pass
    return None


def _setup_mix_sink(mic_source: str, system_monitor: str) -> list[str]:
    """Create null-sink + two loopbacks. Returns list of pactl module IDs."""
    module_ids = []
    r = subprocess.run(
        [
            "pactl",
            "load-module",
            "module-null-sink",
            f"sink_name={_MIX_SINK_NAME}",
            "sink_properties=device.description=LSF_Huddle_Mix",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    module_ids.append(r.stdout.strip())
    r = subprocess.run(
        [
            "pactl",
            "load-module",
            "module-loopback",
            f"source={mic_source}",
            f"sink={_MIX_SINK_NAME}",
            "latency_msec=50",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    module_ids.append(r.stdout.strip())
    r = subprocess.run(
        [
            "pactl",
            "load-module",
            "module-loopback",
            f"source={system_monitor}",
            f"sink={_MIX_SINK_NAME}",
            "latency_msec=50",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    module_ids.append(r.stdout.strip())
    return module_ids


def _teardown_mix_sink(module_ids: list[str]) -> None:
    """Unload pactl modules in reverse order."""
    for mod_id in reversed(module_ids):
        subprocess.run(["pactl", "unload-module", mod_id], capture_output=True)


class HuddleRecorder:
    """Dual-source PulseAudio recorder for Slack huddle sessions.

    Composition: creates a ConversationRecorder pointed at a PulseAudio
    null-sink that mixes the microphone and system audio monitor.

    Threading: same contract as ConversationRecorder — start() called from
    GTK main thread; chunk callbacks dispatched via GLib.idle_add.
    """

    def __init__(
        self,
        mic_device: str | None,
        system_monitor: str | None = None,
        chunk_silence_sec: int = 3,
        silence_rms_threshold: float = 0.005,
    ):
        self._mic_device = mic_device or ""
        self._system_monitor = system_monitor
        self._chunk_silence_sec = chunk_silence_sec
        self._silence_rms_threshold = silence_rms_threshold
        self._module_ids: list[str] = []
        self._recorder: ConversationRecorder | None = None

    def start(
        self,
        on_chunk_ready,
        on_error=None,
        on_audio_level=None,
        on_threshold_calibrated=None,
    ) -> None:
        """Set up null-sink mix and begin recording."""
        monitor = self._system_monitor or get_default_monitor_source()

        mod_id = _existing_sink_module_id(_MIX_SINK_NAME)
        if mod_id:
            logger.warning(
                "Existing lsf-huddle-mix found (crash recovery) — unloading module %s",
                mod_id,
            )
            subprocess.run(["pactl", "unload-module", mod_id], capture_output=True)

        self._module_ids = _setup_mix_sink(self._mic_device, monitor)
        logger.info("Huddle null-sink created: modules %s", self._module_ids)

        self._recorder = ConversationRecorder(
            device_name=_MIX_MONITOR,
            chunk_silence_sec=self._chunk_silence_sec,
            silence_rms_threshold=self._silence_rms_threshold,
        )
        try:
            self._recorder.start(
                on_chunk_ready=on_chunk_ready,
                on_error=on_error,
                on_audio_level=on_audio_level,
                on_threshold_calibrated=on_threshold_calibrated,
            )
        except Exception:
            _teardown_mix_sink(self._module_ids)
            self._module_ids = []
            raise

    def set_threshold(self, value: float) -> None:
        """Delegate silence RMS threshold update to inner ConversationRecorder."""
        if self._recorder:
            self._recorder.set_threshold(value)

    def stop(self) -> None:
        """Stop recording and tear down null-sink."""
        try:
            if self._recorder:
                self._recorder.stop()
                self._recorder = None
        finally:
            if self._module_ids:
                _teardown_mix_sink(self._module_ids)
                self._module_ids = []

    def pause(self) -> None:
        """Pause audio capture without tearing down PulseAudio modules."""
        if self._recorder:
            self._recorder.stop()

    def resume(self) -> None:
        """Resume audio capture without touching PulseAudio modules.

        Caller is responsible for passing on_chunk_ready and on_error again
        via a fresh recorder start if the internal recorder was stopped.
        This delegates to creating a new ConversationRecorder on the same device.
        """
        if self._recorder is None:
            self._recorder = ConversationRecorder(
                device_name=_MIX_MONITOR,
                chunk_silence_sec=self._chunk_silence_sec,
                silence_rms_threshold=self._silence_rms_threshold,
            )

    def cleanup(self) -> None:
        """Remove chunk temp directory."""
        if self._recorder:
            self._recorder.cleanup()
