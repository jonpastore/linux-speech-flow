"""Tests for detect_activation in huddle_manager.py."""
import pytest


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
