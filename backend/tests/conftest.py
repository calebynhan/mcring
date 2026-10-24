import io
import math
import os
import pathlib
import sys

import pytest
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("MCRING_API_TOKEN", "")
os.environ.setdefault("MCRING_TTS_PROVIDER", "none")
os.environ.setdefault("MCRING_STT_PROVIDER", "openai")


@pytest.fixture
def jpeg_bytes():
    img = Image.new("RGB", (320, 240), (200, 30, 90))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


@pytest.fixture
def big_png_bytes():
    img = Image.new("RGB", (3000, 2000), (10, 200, 90))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def sine_pcm(freq_hz: float, rate: int, seconds: float, amp: int = 12000) -> list[int]:
    n = int(rate * seconds)
    return [int(amp * math.sin(2 * math.pi * freq_hz * i / rate)) for i in range(n)]


def zero_crossings(pcm) -> int:
    return sum(1 for a, b in zip(pcm, pcm[1:]) if (a < 0) != (b < 0))


class FakeTTS:
    """Stands in for a TTS provider: 'pcm' returns a 440 Hz sine at 24 kHz, 'mp3' a fake mp3 blob."""

    name = "fake-tts"
    model = "fake-tts-1"
    PCM_RATE = 24000
    SECONDS = 0.5
    FREQ = 440.0

    def __init__(self):
        self.calls = []

    def speak(self, text, voice, fmt):
        self.calls.append({"text": text, "voice": voice, "fmt": fmt})
        if fmt == "mp3":
            return b"ID3fake-mp3-" + text.encode()[:16], "audio/mpeg"
        import struct
        pcm = sine_pcm(self.FREQ, self.PCM_RATE, self.SECONDS)
        return struct.pack(f"<{len(pcm)}h", *pcm), f"audio/pcm;rate={self.PCM_RATE}"


class FakeSTT:
    name = "fake-stt"
    model = "fake-stt-1"

    def __init__(self, text="what is this flower"):
        self.text = text
        self.calls = []

    def transcribe(self, data, filename, language):
        self.calls.append({"data": data, "filename": filename, "language": language})
        return self.text


@pytest.fixture
def fake_tts(monkeypatch):
    from app import tts
    f = FakeTTS()
    monkeypatch.setattr(tts, "get_tts_provider", lambda settings: f)
    return f


@pytest.fixture
def fake_stt(monkeypatch):
    from app import stt
    f = FakeSTT()
    monkeypatch.setattr(stt, "get_stt_provider", lambda settings: f)
    return f


@pytest.fixture
def settings_override():
    """Override the Settings dependency for one test: settings_override(tts_provider='openai')."""
    from app import main
    from app.config import Settings, get_settings

    def _apply(**kw):
        s = Settings(**kw)
        main.app.dependency_overrides[get_settings] = lambda: s
        return s

    yield _apply
    main.app.dependency_overrides.clear()
