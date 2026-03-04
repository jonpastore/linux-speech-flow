"""Tests for OnboardingDialog — first-run welcome + privacy disclosure dialog."""
import pytest

from unittest.mock import MagicMock, patch

gi_patch = patch.dict("sys.modules", {
    "gi": MagicMock(),
    "gi.repository": MagicMock(),
    "gi.repository.Gtk": MagicMock(),
    "gi.repository.GLib": MagicMock(),
})


class TestOnboardingDialog:
    def test_construction(self):
        with gi_patch:
            import sys
            sys.modules.pop("linux_speech_flow.onboarding_dialog", None)
            from linux_speech_flow.onboarding_dialog import OnboardingDialog
            mock_app = MagicMock()
            on_continue = MagicMock()
            on_quit = MagicMock()
            dlg = OnboardingDialog(application=mock_app, on_continue=on_continue, on_quit=on_quit)
            assert dlg is not None

    def test_on_continue_fires(self):
        from linux_speech_flow.onboarding_dialog import OnboardingDialog
        on_continue = MagicMock()
        on_quit = MagicMock()
        dlg = OnboardingDialog.__new__(OnboardingDialog)
        dlg._on_continue = on_continue
        dlg._on_quit = on_quit
        with patch.object(dlg, "close", return_value=None):
            dlg._on_continue_clicked(MagicMock())
        on_continue.assert_called_once()

    def test_on_quit_fires(self):
        from linux_speech_flow.onboarding_dialog import OnboardingDialog
        on_continue = MagicMock()
        on_quit = MagicMock()
        dlg = OnboardingDialog.__new__(OnboardingDialog)
        dlg._on_continue = on_continue
        dlg._on_quit = on_quit
        with patch.object(dlg, "close", return_value=None):
            dlg._on_quit_clicked(MagicMock())
        on_quit.assert_called_once()
