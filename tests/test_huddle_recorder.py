import subprocess
from unittest.mock import MagicMock, patch, call

import pytest

from linux_speech_flow.huddle_recorder import (
    HuddleRecorder,
    get_default_monitor_source,
    _existing_sink_module_id,
    _setup_mix_sink,
    _teardown_mix_sink,
)


class TestGetDefaultMonitorSource:
    def test_returns_default_sink_monitor(self):
        mock_pulse_instance = MagicMock()
        mock_pulse_instance.server_info.return_value.default_sink_name = (
            "alsa_output.pci"
        )
        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: mock_pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = get_default_monitor_source()
        assert result == "alsa_output.pci.monitor"

    def test_appends_dot_monitor_suffix(self):
        mock_pulse_instance = MagicMock()
        mock_pulse_instance.server_info.return_value.default_sink_name = "my_sink"
        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: mock_pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = get_default_monitor_source()
        assert result.endswith(".monitor")


class TestExistingSinkModuleId:
    def test_returns_none_when_no_sink_exists(self):
        mock_pulse_instance = MagicMock()
        mock_pulse_instance.sink_list.return_value = []
        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: mock_pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = _existing_sink_module_id("lsf-huddle-mix")
        assert result is None

    def test_returns_module_id_when_sink_exists(self):
        mock_sink = MagicMock()
        mock_sink.name = "lsf-huddle-mix"
        mock_sink.owner_module = 42
        mock_pulse_instance = MagicMock()
        mock_pulse_instance.sink_list.return_value = [mock_sink]
        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: mock_pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = _existing_sink_module_id("lsf-huddle-mix")
        assert result == "42"

    def test_returns_none_when_different_sink_exists(self):
        mock_sink = MagicMock()
        mock_sink.name = "other-sink"
        mock_sink.owner_module = 99
        mock_pulse_instance = MagicMock()
        mock_pulse_instance.sink_list.return_value = [mock_sink]
        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: mock_pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = _existing_sink_module_id("lsf-huddle-mix")
        assert result is None

    def test_returns_none_on_pulsectl_exception(self):
        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls:
            mock_pulse_cls.side_effect = Exception("connection failed")
            result = _existing_sink_module_id("lsf-huddle-mix")
        assert result is None


class TestSetupMixSink:
    def test_creates_null_sink_and_two_loopbacks(self):
        run_results = [
            MagicMock(stdout="101\n"),
            MagicMock(stdout="102\n"),
            MagicMock(stdout="103\n"),
        ]
        with patch(
            "linux_speech_flow.huddle_recorder.subprocess.run", side_effect=run_results
        ) as mock_run:
            ids = _setup_mix_sink("mic_src", "sys_monitor")

        assert ids == ["101", "102", "103"]
        assert mock_run.call_count == 3

        first_call = mock_run.call_args_list[0]
        cmd = first_call[0][0]
        assert "module-null-sink" in cmd
        assert "sink_name=lsf-huddle-mix" in cmd

        second_call = mock_run.call_args_list[1]
        cmd2 = second_call[0][0]
        assert "module-loopback" in cmd2
        assert "source=mic_src" in cmd2
        assert "sink=lsf-huddle-mix" in cmd2

        third_call = mock_run.call_args_list[2]
        cmd3 = third_call[0][0]
        assert "module-loopback" in cmd3
        assert "source=sys_monitor" in cmd3
        assert "sink=lsf-huddle-mix" in cmd3

    def test_returns_stripped_module_ids(self):
        run_results = [
            MagicMock(stdout="101\n"),
            MagicMock(stdout="102\n"),
            MagicMock(stdout="103\n"),
        ]
        with patch(
            "linux_speech_flow.huddle_recorder.subprocess.run", side_effect=run_results
        ):
            ids = _setup_mix_sink("mic", "monitor")
        for mod_id in ids:
            assert "\n" not in mod_id
            assert mod_id.strip() == mod_id


class TestTeardownMixSink:
    def test_unloads_modules_in_reverse_order(self):
        with patch("linux_speech_flow.huddle_recorder.subprocess.run") as mock_run:
            _teardown_mix_sink(["101", "102", "103"])

        assert mock_run.call_count == 3
        calls = mock_run.call_args_list
        assert calls[0][0][0] == ["pactl", "unload-module", "103"]
        assert calls[1][0][0] == ["pactl", "unload-module", "102"]
        assert calls[2][0][0] == ["pactl", "unload-module", "101"]

    def test_empty_list_makes_no_calls(self):
        with patch("linux_speech_flow.huddle_recorder.subprocess.run") as mock_run:
            _teardown_mix_sink([])
        mock_run.assert_not_called()


class TestHuddleRecorderInit:
    def test_stores_mic_device(self):
        hr = HuddleRecorder("hw:0,0")
        assert hr._mic_device == "hw:0,0"

    def test_empty_string_mic_device(self):
        hr = HuddleRecorder("")
        assert hr._mic_device == ""

    def test_system_monitor_defaults_to_none(self):
        hr = HuddleRecorder("mic")
        assert hr._system_monitor is None

    def test_explicit_system_monitor(self):
        hr = HuddleRecorder("mic", system_monitor="alsa.monitor")
        assert hr._system_monitor == "alsa.monitor"


class TestHuddleRecorderStart:
    def _make_run_side_effects(self):
        return [
            MagicMock(stdout="101\n"),
            MagicMock(stdout="102\n"),
            MagicMock(stdout="103\n"),
        ]

    def _mock_pulse_no_sink(self):
        mock_instance = MagicMock()
        mock_instance.sink_list.return_value = []
        return mock_instance

    def test_start_sets_up_null_sink_before_recorder(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        on_chunk = MagicMock()

        pulse_instance = self._mock_pulse_no_sink()
        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls, patch(
            "linux_speech_flow.huddle_recorder.subprocess.run",
            side_effect=self._make_run_side_effects(),
        ), patch(
            "linux_speech_flow.huddle_recorder.ConversationRecorder"
        ) as mock_recorder_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_recorder = MagicMock()
            mock_recorder_cls.return_value = mock_recorder

            hr.start(on_chunk)

        mock_recorder_cls.assert_called_once_with(
            device_name="lsf-huddle-mix.monitor",
            chunk_silence_sec=3,
            silence_rms_threshold=0.005,
        )
        mock_recorder.start.assert_called_once()

    def test_start_uses_default_monitor_when_none(self):
        hr = HuddleRecorder("mic", system_monitor=None)
        on_chunk = MagicMock()

        pulse_instance = self._mock_pulse_no_sink()
        pulse_instance.server_info.return_value.default_sink_name = "default_sink"

        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls, patch(
            "linux_speech_flow.huddle_recorder.subprocess.run",
            side_effect=self._make_run_side_effects(),
        ) as mock_run, patch(
            "linux_speech_flow.huddle_recorder.ConversationRecorder"
        ) as mock_recorder_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_recorder_cls.return_value = MagicMock()

            hr.start(on_chunk)

        loopback_calls = [
            c for c in mock_run.call_args_list if "module-loopback" in c[0][0]
        ]
        system_loopback = loopback_calls[1][0][0]
        assert "source=default_sink.monitor" in system_loopback

    def test_start_no_crash_recovery_when_sink_absent(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        on_chunk = MagicMock()

        pulse_instance = self._mock_pulse_no_sink()
        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls, patch(
            "linux_speech_flow.huddle_recorder.subprocess.run",
            side_effect=self._make_run_side_effects(),
        ) as mock_run, patch(
            "linux_speech_flow.huddle_recorder.ConversationRecorder"
        ) as mock_recorder_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_recorder_cls.return_value = MagicMock()

            hr.start(on_chunk)

        unload_calls = [
            c for c in mock_run.call_args_list if "unload-module" in c[0][0]
        ]
        assert len(unload_calls) == 0

    def test_start_crash_recovery_unloads_existing_sink(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        on_chunk = MagicMock()

        mock_sink = MagicMock()
        mock_sink.name = "lsf-huddle-mix"
        mock_sink.owner_module = 42
        pulse_instance = MagicMock()
        pulse_instance.sink_list.return_value = [mock_sink]

        load_results = self._make_run_side_effects()
        all_run_results = [MagicMock()] + load_results

        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls, patch(
            "linux_speech_flow.huddle_recorder.subprocess.run",
            side_effect=all_run_results,
        ) as mock_run, patch(
            "linux_speech_flow.huddle_recorder.ConversationRecorder"
        ) as mock_recorder_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_recorder_cls.return_value = MagicMock()

            hr.start(on_chunk)

        first_run_call = mock_run.call_args_list[0][0][0]
        assert "unload-module" in first_run_call
        assert "42" in first_run_call

    def test_start_teardown_on_recorder_start_exception(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        on_chunk = MagicMock()

        pulse_instance = self._mock_pulse_no_sink()
        load_results = self._make_run_side_effects()
        teardown_results = [MagicMock(), MagicMock(), MagicMock()]

        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls, patch(
            "linux_speech_flow.huddle_recorder.subprocess.run"
        ) as mock_run, patch(
            "linux_speech_flow.huddle_recorder.ConversationRecorder"
        ) as mock_recorder_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_run.side_effect = load_results + teardown_results
            mock_recorder = MagicMock()
            mock_recorder.start.side_effect = RuntimeError("recorder error")
            mock_recorder_cls.return_value = mock_recorder

            with pytest.raises(RuntimeError):
                hr.start(on_chunk)

        unload_calls = [
            c for c in mock_run.call_args_list if "unload-module" in c[0][0]
        ]
        assert len(unload_calls) == 3

    def test_start_teardown_clears_module_ids_on_exception(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        on_chunk = MagicMock()
        pulse_instance = self._mock_pulse_no_sink()
        load_results = self._make_run_side_effects()
        teardown_results = [MagicMock(), MagicMock(), MagicMock()]

        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls, patch(
            "linux_speech_flow.huddle_recorder.subprocess.run",
            side_effect=load_results + teardown_results,
        ), patch(
            "linux_speech_flow.huddle_recorder.ConversationRecorder"
        ) as mock_recorder_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_recorder = MagicMock()
            mock_recorder.start.side_effect = RuntimeError("fail")
            mock_recorder_cls.return_value = mock_recorder

            with pytest.raises(RuntimeError):
                hr.start(on_chunk)

        assert hr._module_ids == []


class TestHuddleRecorderStop:
    def _start_recorder(self, hr, pulse_instance):
        on_chunk = MagicMock()
        load_results = [
            MagicMock(stdout="101\n"),
            MagicMock(stdout="102\n"),
            MagicMock(stdout="103\n"),
        ]
        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls, patch(
            "linux_speech_flow.huddle_recorder.subprocess.run", side_effect=load_results
        ), patch(
            "linux_speech_flow.huddle_recorder.ConversationRecorder"
        ) as mock_recorder_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_recorder = MagicMock()
            mock_recorder_cls.return_value = mock_recorder
            hr.start(on_chunk)
            return mock_recorder

    def test_stop_calls_recorder_stop(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        pulse_instance = MagicMock()
        pulse_instance.sink_list.return_value = []
        mock_recorder = self._start_recorder(hr, pulse_instance)

        with patch("linux_speech_flow.huddle_recorder.subprocess.run"):
            hr.stop()

        mock_recorder.stop.assert_called_once()

    def test_stop_calls_teardown(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        pulse_instance = MagicMock()
        pulse_instance.sink_list.return_value = []
        self._start_recorder(hr, pulse_instance)

        with patch("linux_speech_flow.huddle_recorder.subprocess.run") as mock_run:
            hr.stop()

        unload_calls = [
            c for c in mock_run.call_args_list if "unload-module" in c[0][0]
        ]
        assert len(unload_calls) == 3

    def test_stop_teardown_even_when_recorder_raises(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        pulse_instance = MagicMock()
        pulse_instance.sink_list.return_value = []
        mock_recorder = self._start_recorder(hr, pulse_instance)
        mock_recorder.stop.side_effect = RuntimeError("recorder crash")

        with patch("linux_speech_flow.huddle_recorder.subprocess.run") as mock_run:
            with pytest.raises(RuntimeError):
                hr.stop()

        unload_calls = [
            c for c in mock_run.call_args_list if "unload-module" in c[0][0]
        ]
        assert len(unload_calls) == 3

    def test_stop_clears_module_ids(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        pulse_instance = MagicMock()
        pulse_instance.sink_list.return_value = []
        self._start_recorder(hr, pulse_instance)

        with patch("linux_speech_flow.huddle_recorder.subprocess.run"):
            hr.stop()

        assert hr._module_ids == []

    def test_stop_clears_recorder_reference(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        pulse_instance = MagicMock()
        pulse_instance.sink_list.return_value = []
        self._start_recorder(hr, pulse_instance)

        with patch("linux_speech_flow.huddle_recorder.subprocess.run"):
            hr.stop()

        assert hr._recorder is None


class TestHuddleRecorderCleanup:
    def test_cleanup_delegates_to_recorder(self):
        hr = HuddleRecorder("mic", system_monitor="sys.monitor")
        on_chunk = MagicMock()
        pulse_instance = MagicMock()
        pulse_instance.sink_list.return_value = []
        load_results = [
            MagicMock(stdout="101\n"),
            MagicMock(stdout="102\n"),
            MagicMock(stdout="103\n"),
        ]
        with patch(
            "linux_speech_flow.huddle_recorder.pulsectl.Pulse"
        ) as mock_pulse_cls, patch(
            "linux_speech_flow.huddle_recorder.subprocess.run", side_effect=load_results
        ), patch(
            "linux_speech_flow.huddle_recorder.ConversationRecorder"
        ) as mock_recorder_cls:
            mock_pulse_cls.return_value.__enter__ = lambda s: pulse_instance
            mock_pulse_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_recorder = MagicMock()
            mock_recorder_cls.return_value = mock_recorder
            hr.start(on_chunk)

        hr.cleanup()
        mock_recorder.cleanup.assert_called_once()

    def test_cleanup_noop_when_no_recorder(self):
        hr = HuddleRecorder("mic")
        hr.cleanup()
