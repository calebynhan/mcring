import base64

import pytest
from fastapi.testclient import TestClient

from mcring_core import adpcm as adpcm_codec

from app import main, tts
from app.config import Settings
from app.errors import ProviderError

from conftest import zero_crossings


@pytest.fixture
def client():
    return TestClient(main.app)


def test_speech_get_mp3(client, fake_tts, settings_override):
    settings_override(tts_provider="openai", tts_voice="alloy")
    r = client.get("/v1/speech", params={"text": "Hello there"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("audio/mpeg")
    assert r.content.startswith(b"ID3")
    assert r.headers["x-mcring-format"] == "mp3" and r.headers["x-mcring-voice"] == "alloy"
    assert fake_tts.calls[0] == {"text": "Hello there", "voice": "alloy", "fmt": "mp3"}


def test_speech_post_adpcm16k_decodes_to_right_length(client, fake_tts, settings_override):
    settings_override(tts_provider="openai")
    r = client.post("/v1/speech", json={"text": "Hello there", "format": "adpcm16k", "voice": "coral"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("audio/x-mcring-adpcm")
    assert r.headers["x-mcring-sample-rate"] == "16000"
    blob = r.content
    # fake TTS: 0.5 s of 440 Hz at 24 kHz = 12000 samples -> 8000 @ 16 kHz -> 32 blocks of 256
    assert len(blob) == 32 * 132
    assert r.headers["x-mcring-blocks"] == "32" and r.headers["x-mcring-duration-ms"] == "512"
    pcm = adpcm_codec.decode(blob)
    assert len(pcm) == 8192
    # the tone survives resampling + ADPCM: ~880 zero crossings per second over the real 0.5 s
    assert abs(zero_crossings(pcm[:8000]) - 440) <= 6
    assert fake_tts.calls[0]["fmt"] == "pcm" and fake_tts.calls[0]["voice"] == "coral"


def test_speech_json_when_asked(client, fake_tts, settings_override):
    settings_override(tts_provider="openai")
    r = client.get("/v1/speech", params={"text": "Hi", "format": "adpcm16k"}, headers={"Accept": "application/json"})
    assert r.status_code == 200
    j = r.json()
    assert j["format"] == "adpcm16k" and j["blocks"] == 32 and j["sample_rate"] == 16000
    assert len(base64.b64decode(j["audio_b64"])) == 32 * 132


def test_speech_without_provider_is_501(client):
    r = client.get("/v1/speech", params={"text": "Hi"})
    assert r.status_code == 501
    assert "MCRING_TTS_PROVIDER" in r.json()["detail"]


def test_speech_bad_format_and_empty_text(client, fake_tts, settings_override):
    settings_override(tts_provider="openai")
    assert client.get("/v1/speech", params={"text": "Hi", "format": "wav"}).status_code == 400
    assert client.post("/v1/speech", json={"text": "Hi", "format": "wav"}).status_code == 422
    assert client.get("/v1/speech", params={"text": ""}).status_code == 422
    assert client.post("/v1/speech", json={"text": "   "}).status_code == 400


def test_synthesize_truncates_long_text(fake_tts):
    s = Settings(tts_provider="openai", max_speech_chars=40)
    res = tts.synthesize("word " * 50, s, fmt="mp3")
    assert res.format == "mp3" and len(fake_tts.calls[0]["text"]) <= 40


def test_synthesize_rejects_undecodable_provider_audio(monkeypatch):
    class Mp3Only:
        name, model = "mp3only", "x"

        def speak(self, text, voice, fmt):
            return b"ID3...", "audio/mpeg"

    monkeypatch.setattr(tts, "get_tts_provider", lambda s: Mp3Only())
    with pytest.raises(ProviderError) as ei:
        tts.synthesize("hi", Settings(tts_provider="openai"), fmt="adpcm16k")
    assert ei.value.status == 501


def test_get_tts_provider_none_and_unknown():
    with pytest.raises(ProviderError) as ei:
        tts.get_tts_provider(Settings(tts_provider="none"))
    assert ei.value.status == 501
    with pytest.raises(ProviderError) as ei:
        tts.get_tts_provider(Settings(tts_provider="polly"))
    assert ei.value.status == 501


def test_openai_tts_needs_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import sys, types
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=object))
    with pytest.raises(ProviderError) as ei:
        tts.OpenAITTS(Settings(tts_provider="openai"))
    assert ei.value.status == 501 and "OPENAI_API_KEY" in str(ei.value)
