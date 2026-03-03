"""Tests for injector.py — clipboard and paste operations.

All subprocess calls are mocked to avoid requiring xclip/xdotool/wl-copy
to be installed and to avoid actual X11 side effects.
"""
import os
from unittest.mock import MagicMock, patch, call

import pytest

from linux_speech_flow.injector import paste_text, copy_to_clipboard


# ---------------------------------------------------------------------------
# copy_to_clipboard
# ---------------------------------------------------------------------------

class TestCopyToClipboard:

    def test_x11_calls_xclip_clipboard_selection(self):
        with patch("linux_speech_flow.injector.os.environ.get", return_value="x11"), \
             patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            copy_to_clipboard("hello world")

            calls = mock_popen.call_args_list
            cmds = [c[0][0] for c in calls]
            assert ["xclip", "-selection", "clipboard"] in cmds

    def test_x11_calls_xclip_primary_selection(self):
        with patch("linux_speech_flow.injector.os.environ.get", return_value="x11"), \
             patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            copy_to_clipboard("hello world")

            cmds = [c[0][0] for c in mock_popen.call_args_list]
            assert ["xclip", "-selection", "primary"] in cmds

    def test_x11_writes_text_to_stdin(self):
        with patch("linux_speech_flow.injector.os.environ.get", return_value="x11"), \
             patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            copy_to_clipboard("test text")

            mock_proc.stdin.write.assert_called_with(b"test text")

    def test_x11_xclip_not_found_logs_warning(self, caplog):
        import logging
        with patch("linux_speech_flow.injector.os.environ.get", return_value="x11"), \
             patch("linux_speech_flow.injector.subprocess.Popen",
                   side_effect=FileNotFoundError):
            with caplog.at_level(logging.WARNING, logger="linux_speech_flow.injector"):
                copy_to_clipboard("text")
            assert "xclip not found" in caplog.text

    def test_wayland_calls_wl_copy(self):
        with patch("linux_speech_flow.injector.os.environ.get", return_value="wayland"), \
             patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            copy_to_clipboard("wayland text")

            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            assert cmd == ["wl-copy"]

    def test_wayland_uses_communicate(self):
        with patch("linux_speech_flow.injector.os.environ.get", return_value="wayland"), \
             patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            copy_to_clipboard("wayland text")

            mock_proc.communicate.assert_called_once_with(b"wayland text")

    def test_wayland_wl_copy_not_found_logs_warning(self, caplog):
        import logging
        with patch("linux_speech_flow.injector.os.environ.get", return_value="wayland"), \
             patch("linux_speech_flow.injector.subprocess.Popen",
                   side_effect=FileNotFoundError):
            with caplog.at_level(logging.WARNING, logger="linux_speech_flow.injector"):
                copy_to_clipboard("text")
            assert "wl-copy not found" in caplog.text

    def test_unicode_text_encoded_as_utf8(self):
        with patch("linux_speech_flow.injector.os.environ.get", return_value="x11"), \
             patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            copy_to_clipboard("café résumé")

            mock_proc.stdin.write.assert_called_with("café résumé".encode("utf-8"))


# ---------------------------------------------------------------------------
# paste_text (X11 paths)
# ---------------------------------------------------------------------------

class TestPasteTextX11:

    def _x11_window_info(self, window_id="12345", category="other", wm_class="gedit"):
        return {
            "session": "x11",
            "window_id": window_id,
            "category": category,
            "wm_class": wm_class,
        }

    def test_standard_window_sends_ctrl_v(self):
        with patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen, \
             patch("linux_speech_flow.injector.subprocess.run") as mock_run, \
             patch("linux_speech_flow.injector.time.sleep"), \
             patch.dict(os.environ, {"DISPLAY": ":0"}):
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            paste_text("hello", self._x11_window_info())

            run_cmds = [c[0][0] for c in mock_run.call_args_list]
            assert any("ctrl+v" in cmd for cmd in run_cmds)

    def test_terminal_window_sends_ctrl_shift_v(self):
        with patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen, \
             patch("linux_speech_flow.injector.subprocess.run") as mock_run, \
             patch("linux_speech_flow.injector.time.sleep"), \
             patch.dict(os.environ, {"DISPLAY": ":0"}):
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            paste_text("hello", self._x11_window_info(category="terminal"))

            run_cmds = [c[0][0] for c in mock_run.call_args_list]
            assert any("ctrl+shift+v" in cmd for cmd in run_cmds)

    def test_vim_window_sends_shift_insert(self):
        with patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen, \
             patch("linux_speech_flow.injector.subprocess.run") as mock_run, \
             patch("linux_speech_flow.injector.time.sleep"), \
             patch.dict(os.environ, {"DISPLAY": ":0"}):
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            info = self._x11_window_info(wm_class="gvim")
            paste_text("hello", info)

            run_cmds = [c[0][0] for c in mock_run.call_args_list]
            assert any("shift+Insert" in cmd for cmd in run_cmds)

    def test_vim_sends_backspace_for_leaked_f9(self):
        with patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen, \
             patch("linux_speech_flow.injector.subprocess.run") as mock_run, \
             patch("linux_speech_flow.injector.time.sleep"), \
             patch.dict(os.environ, {"DISPLAY": ":0"}):
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            info = self._x11_window_info(wm_class="gvim")
            info["leaked_f9_count"] = 2  # start + stop both F9

            paste_text("hello", info)

            # Find the BackSpace call
            bs_calls = [
                c for c in mock_run.call_args_list
                if "BackSpace" in str(c)
            ]
            assert len(bs_calls) == 1
            bs_cmd = bs_calls[0][0][0]
            # --repeat count should be 2 * 4 = 8
            repeat_idx = bs_cmd.index("--repeat")
            assert bs_cmd[repeat_idx + 1] == "8"

    def test_no_display_skips_xdotool(self):
        with patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen, \
             patch("linux_speech_flow.injector.subprocess.run") as mock_run, \
             patch("linux_speech_flow.injector.time.sleep"), \
             patch.dict(os.environ, {}, clear=True):
            # Remove DISPLAY from env
            env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
            with patch.dict(os.environ, env, clear=True):
                paste_text("hello", self._x11_window_info())

            mock_run.assert_not_called()

    def test_activates_window_before_keystroke(self):
        with patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen, \
             patch("linux_speech_flow.injector.subprocess.run") as mock_run, \
             patch("linux_speech_flow.injector.time.sleep"), \
             patch.dict(os.environ, {"DISPLAY": ":0"}):
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            paste_text("hello", self._x11_window_info(window_id="999"))

            activate_calls = [
                c for c in mock_run.call_args_list
                if "windowactivate" in str(c)
            ]
            assert len(activate_calls) == 1


# ---------------------------------------------------------------------------
# paste_text (Wayland path)
# ---------------------------------------------------------------------------

class TestPasteTextWayland:

    def test_wayland_calls_wl_copy(self):
        with patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            paste_text("wayland text", {"session": "wayland"})

            mock_popen.assert_called_once()
            assert mock_popen.call_args[0][0] == ["wl-copy"]

    def test_wayland_does_not_call_xdotool(self):
        with patch("linux_speech_flow.injector.subprocess.Popen") as mock_popen, \
             patch("linux_speech_flow.injector.subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            paste_text("text", {"session": "wayland"})

            # subprocess.run should not be called (that's for xdotool)
            mock_run.assert_not_called()

    def test_wayland_wl_copy_missing_silent(self):
        with patch("linux_speech_flow.injector.subprocess.Popen",
                   side_effect=FileNotFoundError):
            # Should not raise
            paste_text("text", {"session": "wayland"})
