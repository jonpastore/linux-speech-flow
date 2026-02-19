import importlib.resources
import subprocess
from pathlib import Path


def play_sound(
    sound_name: str,
    output_device: str | None = None,
    enabled: bool = True,
    sound_path: str | None = None,
) -> None:
    """Play a sound file non-blocking via paplay.

    Args:
        sound_name: Bundled filename in linux_speech_flow/sounds/ (e.g. 'start.wav').
        output_device: PulseAudio sink name. None or empty string = system default.
        enabled: If False, this function is a no-op (sounds_enabled=False in config).
        sound_path: Absolute path to a custom WAV file. If set and the file exists,
            overrides the bundled sound. Falls back to bundled sound if missing.
    """
    if not enabled:
        return
    cmd = ["paplay"]
    if output_device:
        cmd.append(f"--device={output_device}")
    if sound_path and Path(sound_path).is_file():
        cmd.append(sound_path)
        subprocess.Popen(cmd, stderr=subprocess.DEVNULL)
    else:
        ref = importlib.resources.files("linux_speech_flow.sounds").joinpath(sound_name)
        with importlib.resources.as_file(ref) as path:
            cmd.append(str(path))
            subprocess.Popen(cmd, stderr=subprocess.DEVNULL)
