import json
import os
import shutil
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "linux-speech-flow" / "config.json"
CONFIG_DIR = CONFIG_PATH.parent

OLD_CONFIG_DIR = Path.home() / ".config" / "freeflow"


def _migrate_legacy_config() -> None:
    """One-time migrations: directory rename and default value updates."""
    if OLD_CONFIG_DIR.exists():
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

    # Migrate Phase 6 silence timer defaults (180/300) to Phase 6.2 defaults (30/60).
    # Only updates values that are still at the original Phase 6 defaults.
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
            changed = False
            if data.get("conv_silence_warn_sec") == 180:
                data["conv_silence_warn_sec"] = 30
                changed = True
            if data.get("conv_silence_stop_sec") == 300:
                data["conv_silence_stop_sec"] = 60
                changed = True
            if changed:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                with open(CONFIG_PATH, "w") as f:
                    json.dump(data, f, indent=2)
                os.chmod(CONFIG_PATH, 0o600)
        except Exception:
            pass


DEFAULT_CONFIG = {
    "groq_api_key": "",
    "microphone": "",
    "vocabulary": [],
    "setup_complete": False,
    # Phase 2 additions
    "sounds_enabled": True,
    "sounds_output_device": "",  # empty string = system default PulseAudio sink
    "max_recording_duration": 300,  # seconds (1–600)
    "silence_stop_duration": 10,  # seconds of silence before auto-stop (1–60)
    # Phase 3 additions
    "whisper_model": "whisper-large-v3-turbo",
    "llm_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "pipeline_timeout": 60,
    "processing_sound_enabled": True,
    "processing_sound_file": "",  # empty = use bundled processing.wav
    "success_sound_enabled": True,
    "success_sound_file": "",  # empty = use bundled success.wav
    "app_categories": {
        "terminals": [
            "gnome-terminal",
            "kitty",
            "alacritty",
            "xterm",
            "konsole",
            "tilix",
            "xfce4-terminal",
        ],
        "editors": [
            "code",
            "vim",
            "nvim",
            "neovim",
            "emacs",
            "sublime_text",
            "gedit",
            "kate",
        ],
    },
    # Phase 5 additions
    "history_max_entries": 20,
    "history_window_width": 700,
    "history_window_height": 500,
    "llm_system_prompt": (
        "You are a transcription cleanup assistant. The user dictated the text below.\n"
        "Your task:\n"
        "- Remove filler words (um, uh, like, you know)\n"
        "- Fix obvious repetitions\n"
        "- Improve sentence flow without changing meaning or paraphrasing\n"
        "- Preserve the user's original casing intent; do not auto-capitalize unless clearly a sentence start\n"
        "- Add terminal punctuation only if the output is clearly a complete sentence; leave fragments without punctuation\n"
        '- Interpret spoken formatting commands literally: "new line" becomes a newline character, "new paragraph" becomes two newlines\n\n'
        "Return ONLY the cleaned text. No explanations, no prefixes, no markdown."
    ),
    # Phase 6 additions
    "conv_silence_warn_sec": 30,  # seconds of session silence before GTK prompt
    "conv_silence_stop_sec": 60,  # seconds of silence before auto-stop (after warn dismissed)
    "conv_hard_limit_sec": 14400,  # 4 hours in seconds; hard recording limit
    "conv_chunk_silence_sec": 3,  # intra-session chunk boundary silence (ConversationRecorder)
    "conv_chunk_max_sec": 20,    # force chunk boundary after N seconds even without silence
    "conv_silence_rms_threshold": 0.005,  # RMS amplitude below which audio is classified as silence (0.0–0.05)
    "conv_save_dir": "~/Documents/conversations",  # expanded at use time via Path.expanduser()
    "conv_feedback_mode": "status_window",  # "tray_only" or "status_window"
    "conv_default_prompt": (
        "Analyze the following conversation transcript. Produce a structured output with:\n"
        "- An executive summary (2–4 paragraphs)\n"
        "- A list of key decisions made\n"
        "- A list of action items with owners if identifiable\n"
        "Calibrate detail level to the audience and complexity indicated by the qualifying answers."
    ),
    "conv_qualifying_questions": [
        "Who is the intended audience? (e.g., technical team, executive, general public)",
        "What is the primary purpose? (e.g., meeting notes, brain dump, planning session, client call)",
        "What is the desired output complexity? (e.g., concise summary, detailed action plan, full transcript only)",
        "Are there specific deliverables expected? (e.g., requirements doc, email, Jira tickets)",
        "Any context the AI should know? (e.g., project name, key names, terminology)",
    ],
    "conv_max_qa_iterations": 3,  # default Q&A rounds before "continue?" prompt
    "conv_auto_analyze": True,  # pre-check AI analysis in post-stop dialog
    "conv_groq_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "grok_api_key": "",
    "grok_model": "grok-3-mini",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "conv_meta_model": "groq",  # which model performs synthesis: "groq", "grok", "gemini"
    "conv_viewer_width": 900,
    "conv_viewer_height": 600,
    # Phase 7 additions
    "hotkey_record": "ctrl+alt+r",
    "hotkey_stop": "ctrl+alt+r",
    "hotkey_conversation": "ctrl+alt+c",
    "hotkey_reprocess": "ctrl+alt+p",
    "hotkey_feedback": "ctrl+alt+f",
    # Phase 8 additions
    "hotkey_huddle": "ctrl+alt+h",
    "slack_workspaces": {},
    "slack_huddle_auto_detect": "prompt",
    "slack_activation_word": "conyo",
    "slack_confidence_threshold": 0.6,
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
