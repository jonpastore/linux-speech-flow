#!/usr/bin/env python3
"""Dev script: generate bundled WAV sound files for linux-speech-flow.
Run from the repo root: python src/linux_speech_flow/scripts/generate_sounds.py
"""
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 22050
AMPLITUDE = 0.3
OUT_DIR = Path(__file__).parent.parent / "sounds"


def generate_tone(freq_hz: float, duration_s: float, fade_s: float = 0.01) -> bytes:
    n = int(SAMPLE_RATE * duration_s)
    fade = int(SAMPLE_RATE * fade_s)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        val = AMPLITUDE * math.sin(2 * math.pi * freq_hz * t)
        if i < fade:
            val *= i / fade
        elif i > n - fade:
            val *= (n - i) / fade
        samples.append(max(-32767, min(32767, int(val * 32767))))
    return struct.pack(f"{n}h", *samples)


def write_wav(path: Path, data: bytes) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(data)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    start_data = generate_tone(440, 0.15) + generate_tone(880, 0.15)
    write_wav(OUT_DIR / "start.wav", start_data)
    print(f"Written: {OUT_DIR / 'start.wav'}")

    stop_data = generate_tone(880, 0.15) + generate_tone(440, 0.15)
    write_wav(OUT_DIR / "stop.wav", stop_data)
    print(f"Written: {OUT_DIR / 'stop.wav'}")

    buzz = generate_tone(200, 0.1, fade_s=0.005)
    silence = bytes(int(SAMPLE_RATE * 0.05) * 2)
    error_data = buzz + silence + buzz + silence + buzz
    write_wav(OUT_DIR / "error.wav", error_data)
    print(f"Written: {OUT_DIR / 'error.wav'}")

    proc_data = generate_tone(523, 0.1) + generate_tone(659, 0.1)
    write_wav(OUT_DIR / "processing.wav", proc_data)
    print(f"Written: {OUT_DIR / 'processing.wav'}")

    succ_data = (
        generate_tone(523, 0.1) + generate_tone(659, 0.1) + generate_tone(784, 0.15)
    )
    write_wav(OUT_DIR / "success.wav", succ_data)
    print(f"Written: {OUT_DIR / 'success.wav'}")

    print("Done.")


if __name__ == "__main__":
    main()
