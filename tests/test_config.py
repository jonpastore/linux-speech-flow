import json
import os
import stat

import pytest

import linux_speech_flow.config as config_module
from linux_speech_flow.config import load_config, save_config, DEFAULT_CONFIG, CONFIG_PATH


def test_load_config_no_file_returns_defaults(tmp_path):
    fake_path = tmp_path / "config.json"
    result = load_config(_path=fake_path)
    assert result["setup_complete"] is False
    assert result["vocabulary"] == []
    assert result["groq_api_key"] == ""
    assert result["microphone"] == ""


def test_load_config_returns_all_default_keys(tmp_path):
    fake_path = tmp_path / "config.json"
    result = load_config(_path=fake_path)
    for key in DEFAULT_CONFIG:
        assert key in result


def test_save_load_round_trip(tmp_path):
    fake_path = tmp_path / "config.json"
    cfg = {
        "groq_api_key": "gsk_test123",
        "microphone": "alsa_input.pci",
        "vocabulary": ["kubernetes", "OAuth"],
        "setup_complete": True,
    }
    save_config(cfg, _path=fake_path)
    result = load_config(_path=fake_path)
    for key, value in cfg.items():
        assert result[key] == value
    for key in DEFAULT_CONFIG:
        assert key in result


def test_save_config_creates_directory(tmp_path):
    nested = tmp_path / "subdir" / "config.json"
    cfg = dict(DEFAULT_CONFIG)
    save_config(cfg, _path=nested)
    assert nested.exists()


def test_save_config_permissions_are_0600(tmp_path):
    fake_path = tmp_path / "config.json"
    cfg = dict(DEFAULT_CONFIG)
    save_config(cfg, _path=fake_path)
    mode = oct(stat.S_IMODE(os.stat(fake_path).st_mode))
    assert mode == "0o600"


def test_save_config_writes_pretty_json(tmp_path):
    fake_path = tmp_path / "config.json"
    cfg = dict(DEFAULT_CONFIG)
    save_config(cfg, _path=fake_path)
    raw = fake_path.read_text()
    assert "\n" in raw


def test_load_config_partial_file_fills_defaults(tmp_path):
    fake_path = tmp_path / "config.json"
    fake_path.write_text(json.dumps({"groq_api_key": "abc"}))
    result = load_config(_path=fake_path)
    assert result["groq_api_key"] == "abc"
    assert result["setup_complete"] is False
    assert result["vocabulary"] == []
    assert result["microphone"] == ""


def test_vocabulary_saves_and_loads_as_list(tmp_path):
    fake_path = tmp_path / "config.json"
    cfg = dict(DEFAULT_CONFIG)
    cfg["vocabulary"] = ["kubernetes", "OAuth"]
    save_config(cfg, _path=fake_path)
    result = load_config(_path=fake_path)
    assert result["vocabulary"] == ["kubernetes", "OAuth"]
    assert isinstance(result["vocabulary"], list)
    assert all(isinstance(v, str) for v in result["vocabulary"])


def test_setup_complete_true_loads_as_bool(tmp_path):
    fake_path = tmp_path / "config.json"
    cfg = dict(DEFAULT_CONFIG)
    cfg["setup_complete"] = True
    save_config(cfg, _path=fake_path)
    result = load_config(_path=fake_path)
    assert result["setup_complete"] is True
    assert isinstance(result["setup_complete"], bool)


def test_config_path_is_xdg_location():
    from pathlib import Path
    expected = Path.home() / ".config" / "linux-speech-flow" / "config.json"
    assert CONFIG_PATH == expected
