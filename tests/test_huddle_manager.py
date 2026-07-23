"""Tests for detect_activation and _wav_avg_rms in huddle_manager.py."""

import os
import struct
import tempfile
import wave


def test_detect_activation_stop_recording():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo stop recording now", "conyo")
    assert cmd == "stop recording"
    assert rest == "now"


def test_detect_activation_no_match():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("hello world", "conyo")
    assert cmd is None
    assert rest is None


def test_detect_activation_case_insensitive():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("CONYO SUMMARIZE please", "conyo")
    assert cmd == "summarize"
    assert rest == "please"


def test_detect_activation_note():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo note this is important", "conyo")
    assert cmd == "note"
    assert rest == "this is important"


def test_detect_activation_topic():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo topic sprint planning", "conyo")
    assert cmd == "topic"
    assert rest == "sprint planning"


def test_detect_activation_help():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo help", "conyo")
    assert cmd == "help"
    assert rest == ""


def test_detect_activation_list_action_items():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo list action items now", "conyo")
    assert cmd == "list action items"
    assert rest == "now"


def test_detect_activation_custom_word():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("hey bot summarize", "hey bot")
    assert cmd == "summarize"
    assert rest == ""


def test_detect_activation_pause():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo pause", "conyo")
    assert cmd == "pause"
    assert rest == ""


def test_detect_activation_resume():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo resume", "conyo")
    assert cmd == "resume"
    assert rest == ""


def test_detect_activation_start_recording():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo start recording", "conyo")
    assert cmd == "start recording"
    assert rest == ""


def test_detect_activation_calibrate():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo calibrate", "conyo")
    assert cmd == "calibrate"
    assert rest == ""


def test_detect_activation_punctuation_after_word():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, _rest = detect_activation("Lucifer, stop recording.", "lucifer")
    assert cmd == "stop recording"


def test_detect_activation_mid_chunk():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, _rest = detect_activation(
        "we were talking about the project then lucifer stop recording", "lucifer"
    )
    assert cmd == "stop recording"


def test_detect_activation_alias_stop():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, _rest = detect_activation("conyo stop", "conyo")
    assert cmd == "stop recording"


def test_detect_activation_alias_start():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, _rest = detect_activation("conyo start", "conyo")
    assert cmd == "start recording"


def test_detect_activation_punctuation_mid_chunk():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, _rest = detect_activation("blah blah blah. Lucifer, summarize!", "lucifer")
    assert cmd == "summarize"


def test_detect_activation_status():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo status", "conyo")
    assert cmd == "status"
    assert rest == ""


def test_detect_activation_word_not_present():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("stop recording now", "conyo")
    assert cmd is None
    assert rest is None


def test_detect_activation_summarize_with_prefix():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("please conyo summarize this", "conyo")
    assert cmd == "summarize"
    assert rest == "this"


def test_detect_activation_partial_match_no_false_positive():
    from linux_speech_flow.huddle_manager import detect_activation

    cmd, rest = detect_activation("conyo unknown-command-xyz", "conyo")
    assert cmd is None
    assert rest is None


def _write_wav(path: str, samples: list[int]) -> None:
    raw = struct.pack(f"{len(samples)}h", *samples)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(raw)


def test_wav_avg_rms_silence():
    from linux_speech_flow.huddle_manager import _wav_avg_rms

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        _write_wav(path, [0] * 1600)
        assert _wav_avg_rms(path) == 0.0
    finally:
        os.unlink(path)


def test_wav_avg_rms_full_scale():
    from linux_speech_flow.huddle_manager import _wav_avg_rms

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        samples = [32767, -32768] * 800
        _write_wav(path, samples)
        rms = _wav_avg_rms(path)
        assert rms > 0.99
    finally:
        os.unlink(path)


def test_wav_avg_rms_missing_file():
    from linux_speech_flow.huddle_manager import _wav_avg_rms

    assert _wav_avg_rms("/tmp/does_not_exist_lsf_test.wav") == 0.0


def test_wav_avg_rms_empty_file():
    from linux_speech_flow.huddle_manager import _wav_avg_rms

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        _write_wav(path, [])
        assert _wav_avg_rms(path) == 0.0
    finally:
        os.unlink(path)
