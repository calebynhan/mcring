import base64
import json

import pytest
from fastapi.testclient import TestClient

from mcring_core import adpcm as adpcm_codec

from app import llm, main
from app.schemas import LLMAnswer

from conftest import sine_pcm


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls = []

    def ask(self, image_bytes, media_type, question, history):
        self.calls.append({"question": question, "history": list(history), "media_type": media_type,
                           "n": len(image_bytes) if image_bytes else 0, "has_image": image_bytes is not None})
        q = question.lower()
        if "edible" in q:
            ans = LLMAnswer(answer="No, foxglove is poisonous.", subject="Digitalis purpurea", confidence=0.9,
                            warnings=["toxic"], follow_up="")
        elif image_bytes is None:
            ans = LLMAnswer(answer="Paris is the capital of France.", subject="Paris", confidence=0.99,
                            warnings=[], follow_up="Want to hear a fun fact about it?")
        elif "blur" in q:
            ans = LLMAnswer(answer="The picture is too blurred to tell. Try another photo.", subject="",
                            confidence=0.2, warnings=[], follow_up="")
        else:
            ans = LLMAnswer(answer="That's a foxglove, Digitalis purpurea. All parts are toxic.",
                            subject="Digitalis purpurea", confidence=0.86, warnings=["toxic if ingested"], follow_up="")
        return llm.LLMResult(answer=ans, provider=self.name, model=self.model, input_tokens=1200, output_tokens=80)


@pytest.fixture
def client(monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(main, "get_provider", lambda name, settings: fake)
    c = TestClient(main.app)
    c.fake = fake
    return c


def wav_bytes(seconds=0.2, rate=16000):
    return adpcm_codec.pcm_to_wav(sine_pcm(300, rate, seconds), rate)


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------
def test_health(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["tts"] == "none" and j["speech_default"] is False
    assert j["speech_formats"] == ["mp3", "adpcm16k"]


# ---------------------------------------------------------------------------
# /v1/ask — photo turns
# ---------------------------------------------------------------------------
def test_ask_with_photo_is_voice_first(client, jpeg_bytes):
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")}, data={"question": "what is this?"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["subject"] == "Digitalis purpurea"
    assert j["answer"].startswith("That's a foxglove")
    assert j["speech_text"] == j["answer"]            # no follow-up -> speech is just the answer
    assert j["mode"] == "identify" and j["had_image"] is True
    # Morse is off by default
    assert j["morse"] is None and j["short"] is None
    # no TTS configured -> no speech, no error (phone speaks speech_text itself)
    assert j["speech"] is None and j["speech_adpcm"] is None and j["speech_error"] is None
    assert j["usage"]["input_tokens"] == 1200
    call = client.fake.calls[0]
    assert call["media_type"] == "image/jpeg" and call["has_image"]
    assert "Identify" in call["question"] and "what is this" in call["question"]


def test_followup_uses_session_and_history(client, jpeg_bytes):
    r1 = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")})
    sid = r1.json()["session_id"]
    r2 = client.post("/v1/ask", data={"session_id": sid, "question": "is it edible?", "mode": "custom"})
    assert r2.status_code == 200, r2.text
    j = r2.json()
    assert j["session_id"] == sid
    assert j["answer"].startswith("No, foxglove")
    assert j["had_image"] is True                      # the session's photo stays referenced
    call = client.fake.calls[1]
    assert call["has_image"] and call["question"].startswith("(The attached photo is the earlier one")
    assert "is it edible?" in call["question"]
    assert len(call["history"]) == 1
    assert json.loads(call["history"][0]["answer_json"])["subject"] == "Digitalis purpurea"


def test_followup_with_default_identify_mode_asks_the_question_verbatim(client, jpeg_bytes):
    """Both companions send their configured mode (default 'identify') on follow-ups; the backend must
    not wrap a follow-up about the session's photo in the identify template."""
    r1 = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")}, data={"mode": "identify"})
    sid = r1.json()["session_id"]
    for mode in ("identify", "describe", "read_text"):
        r2 = client.post("/v1/ask", data={"session_id": sid, "question": "is it edible?", "mode": mode})
        assert r2.status_code == 200, r2.text
        j = r2.json()
        assert j["mode"] == "custom" and j["had_image"] is True
        assert j["answer"].startswith("No, foxglove")
        q = client.fake.calls[-1]["question"]
        assert q == "(The attached photo is the earlier one from this conversation.) is it edible?"
        assert "Identify" not in q and "Describe" not in q and "Read the text" not in q
    # a follow-up with nothing asked still gets the requested template for the carried-over photo
    r3 = client.post("/v1/ask", data={"session_id": sid, "mode": "describe"})
    assert r3.status_code == 200 and r3.json()["mode"] == "describe"
    assert client.fake.calls[-1]["question"].endswith("Describe what is in front of me in one or two sentences.")


def test_new_photo_with_question_keeps_mode_template(client, jpeg_bytes):
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")},
                    data={"question": "is it edible?", "mode": "read_text"})
    assert r.status_code == 200 and r.json()["mode"] == "read_text"
    q = client.fake.calls[0]["question"]
    assert q.startswith("Read the text") and q.endswith("Also: is it edible?")


@pytest.mark.parametrize("mode", ["custom", "chat"])
def test_photo_without_question_in_verbatim_mode_is_identified(client, jpeg_bytes, mode):
    """The app's short-press auto-ask sends the configured mode with no question; 'custom'/'chat' have no
    template, so the photo must fall back to identify instead of a 400."""
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")}, data={"mode": mode})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "identify" and j["had_image"] is True
    assert j["subject"] == "Digitalis purpurea"
    assert client.fake.calls[0]["question"].startswith("What is this? Identify")


def test_photo_with_question_in_custom_mode_is_verbatim(client, jpeg_bytes):
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")},
                    data={"mode": "custom", "question": "how many petals?"})
    assert r.status_code == 200 and r.json()["mode"] == "custom"
    assert client.fake.calls[0]["question"] == "how many petals?"


def test_rejects_garbage_image(client):
    r = client.post("/v1/ask", files={"image": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400


def test_big_png_is_downscaled_and_jpeg(client, big_png_bytes):
    r = client.post("/v1/ask", files={"image": ("big.png", big_png_bytes, "image/png")})
    assert r.status_code == 200
    call = client.fake.calls[0]
    assert call["media_type"] == "image/jpeg"
    assert call["n"] < len(big_png_bytes)


def test_unknown_mode_and_speech_format_rejected(client, jpeg_bytes):
    assert client.post("/v1/ask", data={"question": "hi", "mode": "sing"}).status_code == 400
    assert client.post("/v1/ask", data={"question": "hi", "speech_format": "wav"}).status_code == 400


# ---------------------------------------------------------------------------
# /v1/ask — voice/text chat without a photo
# ---------------------------------------------------------------------------
def test_chat_without_image(client):
    r = client.post("/v1/ask", data={"question": "what's the capital of France?"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "chat" and j["had_image"] is False
    assert j["answer"] == "Paris is the capital of France."
    assert j["follow_up"] == "Want to hear a fun fact about it?"
    assert j["speech_text"] == "Paris is the capital of France. Want to hear a fun fact about it?"
    call = client.fake.calls[0]
    assert call["has_image"] is False and call["media_type"] is None
    assert call["question"] == "what's the capital of France?"     # verbatim, no 'identify' template


def test_chat_mode_explicit_and_multi_turn_memory(client):
    r1 = client.post("/v1/ask", data={"question": "capital of France?", "mode": "chat"})
    sid = r1.json()["session_id"]
    r2 = client.post("/v1/ask", data={"question": "and of Spain?", "mode": "chat", "session_id": sid})
    assert r2.status_code == 200
    call = client.fake.calls[1]
    assert len(call["history"]) == 1 and call["history"][0]["question"] == "capital of France?"
    assert not call["has_image"]


def test_image_mode_without_any_photo_degrades_to_chat(client):
    r = client.post("/v1/ask", data={"question": "how tall is the Eiffel tower?", "mode": "identify"})
    assert r.status_code == 200
    assert r.json()["mode"] == "chat"
    assert client.fake.calls[0]["question"] == "how tall is the Eiffel tower?"


def test_no_question_and_no_photo_is_400(client):
    r = client.post("/v1/ask", data={})
    assert r.status_code == 400
    assert r.json()["detail"] == "say or type a question, or attach a photo"
    for mode in ("identify", "chat", "custom"):
        r = client.post("/v1/ask", data={"mode": mode})
        assert r.status_code == 400


def test_language_hint_without_short_field(client):
    client.post("/v1/ask", data={"question": "hola", "language": "es"})
    q = client.fake.calls[0]["question"]
    assert q.endswith("Answer in es.") and "short" not in q


# ---------------------------------------------------------------------------
# /v1/ask — voice question upload
# ---------------------------------------------------------------------------
def test_ask_with_wav_voice_question(client, fake_stt, jpeg_bytes):
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg"),
                                      "audio": ("q.wav", wav_bytes(), "audio/wav")},
                    data={"mode": "custom"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["transcript"] == "what is this flower"
    assert client.fake.calls[0]["question"] == "what is this flower"
    assert fake_stt.calls[0]["filename"] == "q.wav"


def test_ask_with_ring_adpcm_clip_is_converted_to_wav(client, fake_stt):
    pcm = sine_pcm(300, 16000, 0.5)                       # 8000 samples -> 32 blocks
    clip = adpcm_codec.encode(pcm)
    assert len(clip) == 32 * 132
    r = client.post("/v1/ask", files={"audio": ("voice.adpcm", clip, "audio/x-mcring-adpcm")})
    assert r.status_code == 200, r.text
    assert r.json()["transcript"] == "what is this flower"
    sent = fake_stt.calls[0]
    assert sent["filename"] == "voice.wav" and sent["data"][:4] == b"RIFF"
    assert len(sent["data"]) == 44 + 32 * 256 * 2         # header + decoded 16-bit samples


def test_ask_phone_m4a_passes_through(client, fake_stt):
    m4a = b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 64
    r = client.post("/v1/ask", files={"audio": ("recording", m4a, "audio/mp4")})
    assert r.status_code == 200, r.text
    assert fake_stt.calls[0]["filename"] == "voice.m4a"
    assert fake_stt.calls[0]["data"] == m4a


def test_ask_voice_only_with_stt_unavailable_is_501(client, settings_override):
    settings_override(stt_provider="none")
    r = client.post("/v1/ask", files={"audio": ("q.wav", wav_bytes(), "audio/wav")})
    assert r.status_code == 501
    assert "speech-to-text" in r.json()["detail"]


def test_ask_typed_question_survives_stt_failure(client, settings_override, jpeg_bytes):
    settings_override(stt_provider="none")
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg"),
                                      "audio": ("q.wav", wav_bytes(), "audio/wav")},
                    data={"question": "what is it?"})
    assert r.status_code == 200
    j = r.json()
    assert j["transcript"] is None and "speech-to-text" in j["transcript_error"]


def test_ask_empty_transcript_is_422(client, monkeypatch):
    from app import stt
    from conftest import FakeSTT
    monkeypatch.setattr(stt, "get_stt_provider", lambda s: FakeSTT(text=""))
    r = client.post("/v1/ask", files={"audio": ("q.wav", wav_bytes(), "audio/wav")})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /v1/ask — speech out
# ---------------------------------------------------------------------------
def test_speech_on_by_default_when_tts_configured(client, fake_tts, settings_override):
    settings_override(tts_provider="openai", tts_voice="coral")
    r = client.post("/v1/ask", data={"question": "capital of France?"})
    assert r.status_code == 200, r.text
    j = r.json()
    sp = j["speech"]
    assert sp["format"] == "mp3" and sp["mime"] == "audio/mpeg" and sp["voice"] == "coral"
    assert base64.b64decode(sp["audio_b64"]).startswith(b"ID3")
    assert j["speech_adpcm"] is None
    # follow-up is spoken too
    assert fake_tts.calls[0]["text"] == "Paris is the capital of France. Want to hear a fun fact about it?"


def test_speech_both_formats_and_adpcm_decodes(client, fake_tts, settings_override):
    settings_override(tts_provider="openai")
    r = client.post("/v1/ask", data={"question": "capital of France?", "speech_format": "both", "voice": "sage"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["speech"]["format"] == "mp3"
    ad = j["speech_adpcm"]
    assert ad["format"] == "adpcm16k" and ad["mime"] == "audio/x-mcring-adpcm" and ad["sample_rate"] == 16000
    blob = base64.b64decode(ad["audio_b64"])
    # 0.5 s @ 24 kHz -> 8000 samples @ 16 kHz -> 32 whole blocks (last one zero-padded)
    assert len(blob) == 32 * 132 and ad["blocks"] == 32 and ad["duration_ms"] == 512
    pcm = adpcm_codec.decode(blob)
    assert len(pcm) == 32 * 256
    assert [c["fmt"] for c in fake_tts.calls] == ["mp3", "pcm"]
    assert all(c["voice"] == "sage" for c in fake_tts.calls)


def test_speech_adpcm_only(client, fake_tts, settings_override):
    settings_override(tts_provider="openai")
    r = client.post("/v1/ask", data={"question": "capital of France?", "speech_format": "adpcm16k"})
    j = r.json()
    assert j["speech"] is None and j["speech_adpcm"]["format"] == "adpcm16k"


def test_speech_can_be_turned_off(client, fake_tts, settings_override):
    settings_override(tts_provider="openai")
    r = client.post("/v1/ask", data={"question": "capital of France?", "want_speech": "false"})
    j = r.json()
    assert j["speech"] is None and j["speech_adpcm"] is None and fake_tts.calls == []


def test_speech_requested_without_provider_reports_error_not_failure(client):
    r = client.post("/v1/ask", data={"question": "capital of France?", "want_speech": "true"})
    assert r.status_code == 200
    j = r.json()
    assert j["speech"] is None and "no speech provider" in j["speech_error"]
    assert j["answer"] == "Paris is the capital of France."


# ---------------------------------------------------------------------------
# /v1/ask — optional silent pattern
# ---------------------------------------------------------------------------
def test_want_morse_derives_pattern_from_subject(client, jpeg_bytes):
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")}, data={"want_morse": "true"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["short"] == "DIGITALIS PURPUREA"
    m = j["morse"]
    assert m["text"] == "DIGITALIS PURPUREA"
    assert m["unit_ms"] == 80 and m["units"][0] == 3      # D starts with a dash
    pkt = base64.b64decode(m["ring_packet_b64"])
    assert pkt[0] == 0x14 and pkt[1] == 80 and pkt[2] == 3
    assert int.from_bytes(pkt[3:5], "little") == len(m["units"])
    assert list(pkt[5:]) == m["units"]


def test_want_morse_falls_back_to_answer_and_marks_low_confidence(client, jpeg_bytes):
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")},
                    data={"want_morse": "true", "question": "it's a blur", "mode": "custom"})
    j = r.json()
    assert j["short"].startswith("? THE PICTURE IS TOO BLURRED")
    assert len(j["short"]) <= 32


def test_morse_endpoint(client):
    r = client.post("/v1/morse", json={"text": "sos", "char_wpm": 20, "overall_wpm": 20})
    j = r.json()
    assert j["units"] == [1, 1, 1, 1, 1, 3, 3, 1, 3, 1, 3, 3, 1, 1, 1, 1, 1]
    assert j["unit_ms"] == 60 and j["duration_ms"] == 27 * 60


# ---------------------------------------------------------------------------
# blocking providers must not run on the event loop
# ---------------------------------------------------------------------------
def _on_event_loop() -> bool:
    import asyncio
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def test_stt_llm_and_tts_run_off_the_event_loop(client, settings_override, monkeypatch, jpeg_bytes):
    """The STT/LLM/TTS clients are synchronous network calls; the async handlers must hand them to the
    threadpool, or one voice turn blocks every other request for its whole STT+LLM+TTS latency."""
    from app import stt, tts
    from conftest import FakeSTT, FakeTTS
    seen = {}

    class LoopAwareSTT(FakeSTT):
        def transcribe(self, data, filename, language):
            seen["stt"] = _on_event_loop()
            return super().transcribe(data, filename, language)

    class LoopAwareTTS(FakeTTS):
        def speak(self, text, voice, fmt):
            seen["tts"] = _on_event_loop()
            return super().speak(text, voice, fmt)

    class LoopAwareLLM(FakeProvider):
        def ask(self, *a, **k):
            seen["llm"] = _on_event_loop()
            return super().ask(*a, **k)

    monkeypatch.setattr(stt, "get_stt_provider", lambda s: LoopAwareSTT())
    monkeypatch.setattr(tts, "get_tts_provider", lambda s: LoopAwareTTS())
    monkeypatch.setattr(main, "get_provider", lambda name, settings: LoopAwareLLM())
    settings_override(tts_provider="openai")
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg"),
                                      "audio": ("q.wav", wav_bytes(), "audio/wav")},
                    data={"speech_format": "both"})
    assert r.status_code == 200, r.text
    assert seen == {"stt": False, "llm": False, "tts": False}

    seen.clear()
    r = client.post("/v1/transcribe", files={"audio": ("q.wav", wav_bytes(), "audio/wav")})
    assert r.status_code == 200 and seen == {"stt": False}


# ---------------------------------------------------------------------------
# errors / refusals / auth
# ---------------------------------------------------------------------------
def test_refusal_maps_to_safe_answer(client, jpeg_bytes, monkeypatch):
    class Refusing:
        def ask(self, *a, **k):
            raise llm.ModelRefused()
    monkeypatch.setattr(main, "get_provider", lambda name, settings: Refusing())
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")}, data={"want_morse": "true"})
    assert r.status_code == 200
    j = r.json()
    assert j["answer"] == "I can't help with that one." and j["confidence"] == 0.0
    assert j["short"].startswith("? ")


def test_provider_error_status(client, jpeg_bytes, monkeypatch):
    class Broken:
        def ask(self, *a, **k):
            raise llm.ProviderError("upstream down", status=503, retryable=True)
    monkeypatch.setattr(main, "get_provider", lambda name, settings: Broken())
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")})
    assert r.status_code == 503 and r.json()["retryable"] is True


def test_token_required(monkeypatch, settings_override, fake_stt, fake_tts):
    monkeypatch.setattr(main, "get_provider", lambda name, settings: FakeProvider())
    settings_override(api_token="secret", tts_provider="openai")
    c = TestClient(main.app)
    hdr = {"Authorization": "Bearer secret"}
    assert c.post("/v1/morse", json={"text": "e"}).status_code == 401
    assert c.post("/v1/morse", json={"text": "e"}, headers=hdr).status_code == 200
    assert c.post("/v1/ask", data={"question": "hi"}).status_code == 401
    assert c.post("/v1/ask", data={"question": "hi"}, headers=hdr).status_code == 200
    assert c.get("/v1/speech", params={"text": "hi"}).status_code == 401
    assert c.get("/v1/speech", params={"text": "hi"}, headers=hdr).status_code == 200
    assert c.post("/v1/transcribe", files={"audio": ("q.wav", wav_bytes(), "audio/wav")}).status_code == 401
    assert c.post("/v1/transcribe", files={"audio": ("q.wav", wav_bytes(), "audio/wav")}, headers=hdr).status_code == 200
    assert c.get("/v1/health").status_code == 200       # health stays open
