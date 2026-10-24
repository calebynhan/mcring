import sys

import pytest
from fastapi.testclient import TestClient

from mcring_core import adpcm as adpcm_codec

from app import main, stt
from app.config import Settings
from app.errors import ProviderError

from conftest import sine_pcm


@pytest.fixture
def client():
    return TestClient(main.app)


def wav_bytes(seconds=0.2, rate=16000):
    return adpcm_codec.pcm_to_wav(sine_pcm(300, rate, seconds), rate)


def test_transcribe_wav(client, fake_stt):
    r = client.post("/v1/transcribe", files={"audio": ("q.wav", wav_bytes(), "audio/wav")}, data={"language": "en-US"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["text"] == "what is this flower" and j["audio_format"] == "wav" and j["language"] == "en"
    assert j["provider"] == "fake-stt" and j["model"] == "fake-stt-1"
    assert fake_stt.calls[0]["language"] == "en"


def test_transcribe_ring_adpcm(client, fake_stt):
    clip = adpcm_codec.encode(sine_pcm(300, 16000, 1.0))        # 63 blocks (16000/256 rounded up)
    r = client.post("/v1/transcribe", files={"audio": ("voice.adpcm", clip, "application/octet-stream")})
    assert r.status_code == 200, r.text
    assert r.json()["audio_format"] == "adpcm"
    sent = fake_stt.calls[0]["data"]
    assert sent[:4] == b"RIFF" and len(sent) == 44 + 63 * 256 * 2


def test_transcribe_headerless_adpcm_by_block_size(client, fake_stt):
    clip = adpcm_codec.encode(sine_pcm(300, 16000, 0.3))
    r = client.post("/v1/transcribe", files={"audio": ("blob", clip, "application/octet-stream")})
    assert r.status_code == 200 and r.json()["audio_format"] == "adpcm"


def test_transcribe_unlabelled_adpcm_starting_with_mpeg_sync_word(client, fake_stt):
    """A headerless clip whose first sample is -1 begins FF FF; it must still reach STT as decoded WAV."""
    clip = adpcm_codec.encode([-1] * 256 + sine_pcm(300, 16000, 0.2))
    assert clip[:2] == b"\xff\xff"
    r = client.post("/v1/transcribe", files={"audio": ("blob", clip, "")})
    assert r.status_code == 200, r.text
    assert r.json()["audio_format"] == "adpcm"
    assert fake_stt.calls[-1]["filename"] == "voice.wav" and fake_stt.calls[-1]["data"][:4] == b"RIFF"


def test_transcribe_m4a_and_mp3_pass_through(client, fake_stt):
    m4a = b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 40
    r = client.post("/v1/transcribe", files={"audio": ("rec.m4a", m4a, "audio/x-m4a")})
    assert r.status_code == 200 and r.json()["audio_format"] == "m4a"
    assert fake_stt.calls[-1]["filename"] == "rec.m4a"
    r = client.post("/v1/transcribe", files={"audio": ("x", b"ID3\x04" + b"\x00" * 40, "")})
    assert r.status_code == 200 and r.json()["audio_format"] == "mp3"
    assert fake_stt.calls[-1]["filename"] == "voice.mp3"


def test_transcribe_unknown_format_is_415(client, fake_stt):
    r = client.post("/v1/transcribe", files={"audio": ("x", b"\x01" * 100, "")})
    assert r.status_code == 415


def test_transcribe_empty_is_400(client, fake_stt):
    r = client.post("/v1/transcribe", files={"audio": ("x.wav", b"", "audio/wav")})
    assert r.status_code == 400


def test_transcribe_no_provider_is_501(client, settings_override):
    settings_override(stt_provider="none")
    r = client.post("/v1/transcribe", files={"audio": ("q.wav", wav_bytes(), "audio/wav")})
    assert r.status_code == 501 and "MCRING_STT_PROVIDER" in r.json()["detail"]


def test_local_provider_without_faster_whisper_is_501(client, settings_override, monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)     # force ImportError
    stt._STT.pop("local", None)
    settings_override(stt_provider="local")
    r = client.post("/v1/transcribe", files={"audio": ("q.wav", wav_bytes(), "audio/wav")})
    assert r.status_code == 501
    assert "faster-whisper" in r.json()["detail"]


def test_local_provider_uses_faster_whisper(monkeypatch):
    class Seg:
        def __init__(self, t):
            self.text = t

    class FakeModel:
        def __init__(self, name, device, compute_type):
            self.args = (name, device, compute_type)
            self.calls = []

        def transcribe(self, f, language, beam_size, vad_filter):
            self.calls.append({"n": len(f.read()), "language": language})
            return iter([Seg(" what is "), Seg("this ")]), {"language": "en"}

    import types
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    stt._STT.pop("local", None)
    s = Settings(stt_provider="local", whisper_model="base.en", whisper_device="cpu", whisper_compute_type="int8")
    tr = stt.transcribe(wav_bytes(), "q.wav", "audio/wav", s, language="de")
    assert tr.text == "what is this" and tr.provider == "local" and tr.model == "base.en"
    prov = stt._STT.pop("local")
    assert prov._model.args == ("base.en", "cpu", "int8")
    assert prov._model.calls[0]["language"] == "en"            # *.en models force English


def test_openai_stt_needs_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import types
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=object))
    stt._STT.pop("openai", None)
    with pytest.raises(ProviderError) as ei:
        stt.get_stt_provider(Settings(stt_provider="openai"))
    assert ei.value.status == 501 and "OPENAI_API_KEY" in str(ei.value)


def test_lang_code():
    assert stt._lang_code("en-US") == "en" and stt._lang_code("de") == "de" and stt._lang_code("") is None
    assert stt._lang_code("english") is None and stt._lang_code("pt_BR") == "pt"
