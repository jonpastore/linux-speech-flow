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
            from linux_speech_flow.onboarding_dialog import OnboardingDialog
            mock_app = MagicMock()
            on_continue = MagicMock()
            on_quit = MagicMock()
            dlg = OnboardingDialog(application=mock_app, on_continue=on_continue, on_quit=on_quit)
            assert dlg is not None

    def test_on_continue_fires(self):
        with gi_patch:
            from linux_speech_flow.onboarding_dialog import OnboardingDialog
            mock_app = MagicMock()
            on_continue = MagicMock()
            on_quit = MagicMock()
            dlg = OnboardingDialog(application=mock_app, on_continue=on_continue, on_quit=on_quit)
            dlg._on_continue_clicked(MagicMock())
            on_continue.assert_called_once()

    def test_on_quit_fires(self):
        with gi_patch:
            from linux_speech_flow.onboarding_dialog import OnboardingDialog
            mock_app = MagicMock()
            on_continue = MagicMock()
            on_quit = MagicMock()
            dlg = OnboardingDialog(application=mock_app, on_continue=on_continue, on_quit=on_quit)
            dlg._on_quit_clicked(MagicMock())
            on_quit.assert_called_once()
