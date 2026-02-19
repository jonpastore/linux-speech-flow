import json
import os
import shutil
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "linux-speech-flow" / "config.json"
CONFIG_DIR = CONFIG_PATH.parent

OLD_CONFIG_DIR = Path.home() / ".config" / "freeflow"


def _migrate_legacy_config() -> None:
    """One-time migration: move ~/.config/freeflow/ to ~/.config/linux-speech-flow/."""
    if not OLD_CONFIG_DIR.exists():
        return
    try:
        if not CONFIG_PATH.exists():
            old_config = OLD_CONFIG_DIR / "config.json"
            if old_config.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_config, CONFIG_PATH)
        shutil.rmtree(OLD_CONFIG_DIR, ignore_errors=True)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Config migration failed: %s", exc)

DEFAULT_CONFIG = {
    "groq_api_key": "",
    "microphone": "",
    "vocabulary": [],
    "setup_complete": False,
    # Phase 2 additions
    "sounds_enabled": True,
    "sounds_output_device": "",      # empty string = system default PulseAudio sink
    "max_recording_duration": 300,   # seconds (1–600)
    "silence_stop_duration": 10,     # seconds of silence before auto-stop (1–60)
    # Phase 3 additions
    "whisper_model": "whisper-large-v3-turbo",
    "llm_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "pipeline_timeout": 60,
    "processing_sound_enabled": True,
    "processing_sound_file": "",     # empty = use bundled processing.wav
    "success_sound_enabled": True,
    "success_sound_file": "",        # empty = use bundled success.wav
    "app_categories": {
        "terminals": ["gnome-terminal", "kitty", "alacritty", "xterm", "konsole", "tilix", "xfce4-terminal"],
        "editors": ["code", "vim", "nvim", "neovim", "emacs", "sublime_text", "gedit", "kate"],
    },
    "llm_system_prompt": (
        "You are a transcription cleanup assistant. The user dictated the text below.\n"
        "Your task:\n"
        "- Remove filler words (um, uh, like, you know)\n"
        "- Fix obvious repetitions\n"
        "- Improve sentence flow without changing meaning or paraphrasing\n"
        "- Preserve the user's original casing intent; do not auto-capitalize unless clearly a sentence start\n"
        "- Add terminal punctuation only if the output is clearly a complete sentence; leave fragments without punctuation\n"
        "- Interpret spoken formatting commands literally: \"new line\" becomes a newline character, \"new paragraph\" becomes two newlines\n\n"
        "Return ONLY the cleaned text. No explanations, no prefixes, no markdown."
    ),
}


def load_config(*, _path: Path = CONFIG_PATH) -> dict:
    _migrate_legacy_config()
    config = dict(DEFAULT_CONFIG)
    if _path.exists():
        with open(_path) as f:
            data = json.load(f)
        config.update(data)
    return config


def save_config(config: dict, *, _path: Path = CONFIG_PATH) -> None:
    _path.parent.mkdir(parents=True, exist_ok=True)
    with open(_path, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(_path, 0o600)
