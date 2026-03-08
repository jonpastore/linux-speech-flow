"""Tests for ConversationRecorder chunk recording logic.

pasimple and GLib are mocked throughout — no audio hardware or GTK required.
"""
import math
import os
import struct
import wave
from unittest.mock import MagicMock, call, patch

import pytest

from linux_speech_flow.conversation_recorder import (
    CALIB_FACTOR,
    CALIB_FRAMES,
    CALIB_MAX,
    CALIB_MIN,
    CHUNK_BYTES,
    CHUNK_DURATION,
    MIN_GUARD_FRAMES,
    ConversationRecorder,
)

# ── frame factories ───────────────────────────────────────────────────────────

_N_SAMPLES = CHUNK_BYTES // 2  # int16 = 2 bytes each


def _silence_frame() -> bytes:
    """All-zero audio frame — RMS == 0.0, below any threshold."""
    return b"\x00" * CHUNK_BYTES


def _audio_frame(amplitude: float = 0.1) -> bytes:
    """Frame with constant amplitude. RMS ≈ amplitude >> default threshold 0.005."""
    s = int(amplitude * 32767)
    return struct.pack(f"{_N_SAMPLES}h", *([s] * _N_SAMPLES))


def _rms(frame: bytes) -> float:
    samples = struct.unpack(f"{len(frame) // 2}h", frame)
    return math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0


# ── construction and simple methods ──────────────────────────────────────────


class TestInit:
    def test_defaults(self):
        rec = ConversationRecorder(device_name=None)
        assert rec._device_name is None
        assert rec._chunk_silence_sec == 3
        assert rec._silence_rms_threshold == 0.005
        assert not rec._stop_event.is_set()
        assert os.path.isdir(rec._chunk_dir)
        rec.cleanup()

    def test_custom_params(self):
        rec = ConversationRecorder(
            device_name="hw:0", chunk_silence_sec=5, silence_rms_threshold=0.01
        )
        assert rec._device_name == "hw:0"
        assert rec._chunk_silence_sec == 5
        assert rec._silence_rms_threshold == 0.01
        rec.cleanup()

    def test_empty_device_name_coerced_to_none(self):
        rec = ConversationRecorder(device_name="")
        # __init__ does: self._device_name = device_name or None
        assert rec._device_name is None
        rec.cleanup()


class TestStop:
    def test_sets_stop_event(self):
        rec = ConversationRecorder(device_name=None)
        assert not rec._stop_event.is_set()
        rec.stop()
        assert rec._stop_event.is_set()
        rec.cleanup()

    def test_idempotent(self):
        rec = ConversationRecorder(device_name=None)
        rec.stop()
        rec.stop()
        assert rec._stop_event.is_set()
        rec.cleanup()


class TestCleanup:
    def test_removes_temp_dir(self):
        rec = ConversationRecorder(device_name=None)
        chunk_dir = rec._chunk_dir
        assert os.path.isdir(chunk_dir)
        rec.cleanup()
        assert not os.path.exists(chunk_dir)

    def test_idempotent(self):
        rec = ConversationRecorder(device_name=None)
        rec.cleanup()
        rec.cleanup()  # should not raise


class TestSetThreshold:
    def test_updates_threshold(self):
        rec = ConversationRecorder(device_name=None)
        rec.set_threshold(0.02)
        assert rec._silence_rms_threshold == 0.02
        rec.cleanup()


# ── _record_one_chunk logic ───────────────────────────────────────────────────


def _make_rec(**kw):
    """Convenience: create recorder, register no-op callbacks."""
    rec = ConversationRecorder(device_name=None, **kw)
    rec._on_chunk_ready = MagicMock()
    rec._on_error = MagicMock()
    rec._on_silence_tick = MagicMock()
    rec._on_audio_level = MagicMock()
    rec._on_threshold_calibrated = MagicMock()
    return rec


def _mock_pa_from_seq(rec, frames: list[bytes]):
    """Return a mock pa whose .read() yields frames then sets stop_event."""
    mock_pa = MagicMock()
    call_count = [0]

    def side_read(n):
        i = call_count[0]
        call_count[0] += 1
        if i < len(frames):
            return frames[i]
        rec.stop()
        return _silence_frame()

    mock_pa.read.side_effect = side_read
    return mock_pa


@patch("linux_speech_flow.conversation_recorder.GLib")
class TestRecordOneChunk:
    def test_audio_frames_set_had_audio(self, mock_glib, tmp_path):
        rec = _make_rec()
        frames = [_audio_frame()] * (MIN_GUARD_FRAMES + 5)
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        _, had_audio = rec._record_one_chunk(pa, wav, 100, 0)
        assert had_audio
        rec.cleanup()

    def test_silence_only_had_audio_false(self, mock_glib, tmp_path):
        rec = _make_rec()
        # Only silence (below threshold) after guard
        frames = [_silence_frame()] * (MIN_GUARD_FRAMES + 5)
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        _, had_audio = rec._record_one_chunk(pa, wav, 100, 0)
        assert not had_audio
        rec.cleanup()

    def test_stop_event_exits_loop(self, mock_glib, tmp_path):
        rec = _make_rec()
        frames = [_audio_frame()] * (MIN_GUARD_FRAMES + 3)
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        frames_written, _ = rec._record_one_chunk(pa, wav, 1000, 0)
        # Main loop: MIN_GUARD_FRAMES + 3 audio + 1 stop/silence frame = MIN_GUARD_FRAMES + 4
        # Drain: after stop, reads silence until 1s elapsed (int(1.0/CHUNK_DURATION) frames).
        # stop frame counts as silence_frames=1, so drain reads int(1.0/CHUNK_DURATION)-1 more.
        drain = int(1.0 / CHUNK_DURATION) - 1
        assert frames_written == MIN_GUARD_FRAMES + 4 + drain
        rec.cleanup()

    def test_silence_boundary_exits_chunk(self, mock_glib, tmp_path):
        silence_limit = 3
        rec = _make_rec(silence_rms_threshold=0.001)
        frames = (
            [_audio_frame()] * MIN_GUARD_FRAMES  # guard
            + [_audio_frame()] * 5  # speech
            + [_silence_frame()] * silence_limit  # trigger boundary
        )
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        frames_written, had_audio = rec._record_one_chunk(pa, wav, silence_limit, 0)
        assert had_audio
        assert frames_written == MIN_GUARD_FRAMES + 5 + silence_limit
        rec.cleanup()

    def test_wav_file_created_and_valid(self, mock_glib, tmp_path):
        rec = _make_rec()
        frames = [_audio_frame()] * (MIN_GUARD_FRAMES + 2)
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        rec._record_one_chunk(pa, wav, 100, 0)
        assert os.path.exists(wav)
        with wave.open(wav, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
        rec.cleanup()

    def test_silence_tick_emitted_on_change(self, mock_glib, tmp_path):
        rec = _make_rec()
        # Guard + audio + 2 silence frames
        frames = (
            [_audio_frame()] * MIN_GUARD_FRAMES
            + [_audio_frame()] * 2
            + [_silence_frame()] * 2
        )
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        rec._record_one_chunk(pa, wav, 100, 0)
        # idle_add should have been called with _on_silence_tick at least once
        silence_calls = [
            c
            for c in mock_glib.idle_add.call_args_list
            if c[0][0] == rec._on_silence_tick
        ]
        assert len(silence_calls) >= 1
        rec.cleanup()

    def test_silence_tick_not_emitted_if_unchanged(self, mock_glib, tmp_path):
        rec = _make_rec()
        # 2 consecutive audio frames after guard: only 1 emit for 0 (not 2)
        frames = [_audio_frame()] * MIN_GUARD_FRAMES + [_audio_frame()] * 2
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        rec._record_one_chunk(pa, wav, 100, 0)
        silence_tick_calls = [
            c
            for c in mock_glib.idle_add.call_args_list
            if c[0][0] == rec._on_silence_tick
        ]
        # Two consecutive audio frames after guard: only 1 emit for value 0 (debounced).
        # Stop frame is silence so silence_frames goes to 1 (1 more emit). Total = 2.
        assert len(silence_tick_calls) == 2
        # First emit must be 0 (active speech), not repeated value
        assert silence_tick_calls[0][0][1] == 0
        rec.cleanup()

    def test_audio_level_emitted_after_guard(self, mock_glib, tmp_path):
        rec = _make_rec()
        # MIN_GUARD_FRAMES + 3 seq frames; _mock_pa_from_seq adds 1 stop frame
        # audio_level fires from frame MIN_GUARD_FRAMES onwards = 4 seq + 1 stop = 5
        frames = [_audio_frame(0.2)] * (MIN_GUARD_FRAMES + 3)
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        rec._record_one_chunk(pa, wav, 100, 0)
        level_calls = [
            c
            for c in mock_glib.idle_add.call_args_list
            if c[0][0] == rec._on_audio_level
        ]
        assert len(level_calls) == 5  # frames >= MIN_GUARD_FRAMES: last guard + 3 + stop
        rec.cleanup()

    def test_frames_written_counts_all_frames(self, mock_glib, tmp_path):
        n = MIN_GUARD_FRAMES + 7
        rec = _make_rec()
        frames = [_audio_frame()] * n
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        frames_written, _ = rec._record_one_chunk(pa, wav, 1000, 0)
        # n audio frames + 1 stop/silence frame + drain (int(1.0/CHUNK_DURATION)-1 silence frames)
        drain = int(1.0 / CHUNK_DURATION) - 1
        assert frames_written == n + 1 + drain
        rec.cleanup()


# ── auto-calibration ──────────────────────────────────────────────────────────


@patch("linux_speech_flow.conversation_recorder.GLib")
class TestAutoCalibration:
    def test_calibrates_on_first_chunk(self, mock_glib, tmp_path):
        """Ambient RMS during guard sets threshold = clamp(ambient_25pct * CALIB_FACTOR)."""
        # Use tiny amplitude so calibrated threshold is different from default
        ambient_amplitude = 0.0003  # very quiet
        rec = _make_rec(silence_rms_threshold=0.005)
        frames = [_audio_frame(ambient_amplitude)] * (CALIB_FRAMES + 2)
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        rec._record_one_chunk(pa, wav, 1000, 0)
        # All uniform frames — 25th percentile equals the frame RMS
        ambient_rms = _rms(_audio_frame(ambient_amplitude))
        expected = max(CALIB_MIN, min(CALIB_MAX, ambient_rms * CALIB_FACTOR))
        assert rec._silence_rms_threshold == pytest.approx(expected, rel=0.01)
        rec.cleanup()

    def test_no_calibration_on_subsequent_chunks(self, mock_glib, tmp_path):
        """chunk_index != 0 → calib_done=True at start, threshold unchanged."""
        rec = _make_rec(silence_rms_threshold=0.005)
        frames = [_audio_frame(0.0003)] * (CALIB_FRAMES + 2)
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        rec._record_one_chunk(pa, wav, 1000, chunk_index=1)  # chunk 1 = no calib
        assert rec._silence_rms_threshold == pytest.approx(0.005)
        rec.cleanup()

    def test_calibration_raises_threshold_for_noisy_environment(self, mock_glib, tmp_path):
        """Loud ambient (restaurant music) → calibration fires and raises threshold.

        Previously calibration was skipped when ambient > initial threshold, which
        left the threshold at 0.005 and treated all background noise as speech.
        """
        music_amplitude = 0.015  # restaurant-level background music
        rec = _make_rec(silence_rms_threshold=0.005)
        frames = [_audio_frame(music_amplitude)] * (CALIB_FRAMES + 2)
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        rec._record_one_chunk(pa, wav, 1000, 0)
        # Threshold must be raised above the music floor
        music_rms = _rms(_audio_frame(music_amplitude))
        expected = max(CALIB_MIN, min(CALIB_MAX, music_rms * CALIB_FACTOR))
        assert rec._silence_rms_threshold == pytest.approx(expected, rel=0.01)
        assert rec._silence_rms_threshold > 0.005  # must be higher than default
        rec.cleanup()

    def test_calibration_fires_on_threshold_calibrated_callback(self, mock_glib, tmp_path):
        """on_threshold_calibrated called via GLib.idle_add when calib succeeds."""
        rec = _make_rec(silence_rms_threshold=0.005)
        frames = [_audio_frame(0.0003)] * (CALIB_FRAMES + 2)
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        rec._record_one_chunk(pa, wav, 1000, 0)
        calib_calls = [
            c
            for c in mock_glib.idle_add.call_args_list
            if c[0][0] == rec._on_threshold_calibrated
        ]
        assert len(calib_calls) == 1
        rec.cleanup()

    def test_calibration_clamped_to_calib_min(self, mock_glib, tmp_path):
        """Extremely quiet ambient → threshold clamped to CALIB_MIN."""
        rec = _make_rec(silence_rms_threshold=0.005)
        # Essentially silent guard frames
        frames = [_silence_frame()] * (CALIB_FRAMES + 2)
        pa = _mock_pa_from_seq(rec, frames)
        wav = str(tmp_path / "c.wav")
        rec._record_one_chunk(pa, wav, 1000, 0)
        assert rec._silence_rms_threshold >= CALIB_MIN
        rec.cleanup()
