import base64
import json

import httpx

from mcring_cli.backend_client import BackendClient, audio_mime_for, parse_ask

ADPCM = bytes((i * 7) & 255 for i in range(132 * 3))
ANSWER = {
    "id": "a1", "session_id": "s1", "answer": "A foxglove.", "speech_text": "A foxglove. Want to know if it is toxic?",
    "follow_up": "Want to know if it is toxic?", "subject": "Digitalis purpurea", "confidence": 0.9, "warnings": ["toxic"],
    "mode": "identify", "had_image": True, "transcript": "what is this", "transcript_error": None,
    "speech": {"format": "mp3", "mime": "audio/mpeg", "audio_b64": base64.b64encode(b"\xff\xfbMP3").decode(), "voice": "alloy"},
    "speech_adpcm": {"format": "adpcm16k", "mime": "audio/x-mcring-adpcm", "audio_b64": base64.b64encode(ADPCM).decode(),
                     "voice": "alloy", "sample_rate": 16000, "blocks": 3, "duration_ms": 48},
    "speech_error": None, "short": None, "morse": None, "provider": "anthropic", "model": "claude", "latency_ms": 321,
}


def test_parse_new_shape_without_short():
    r = parse_ask(ANSWER)
    assert r.answer == "A foxglove." and r.follow_up == "Want to know if it is toxic?"
    assert r.speech_text == "A foxglove. Want to know if it is toxic?"
    assert r.short is None and r.morse_units == [] and r.ring_packet is None
    assert r.speech_mp3 == b"\xff\xfbMP3" and r.speech_adpcm == ADPCM
    assert r.transcript == "what is this" and r.had_image and r.warnings == ["toxic"]
    minimal = parse_ask({"answer": "Hi.", "confidence": 0.5, "session_id": "s", "mode": "chat", "had_image": False})
    assert minimal.speech_text == "Hi." and minimal.speech_mp3 is None and minimal.follow_up is None


def test_ask_request_is_voice_first_and_parses():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["body"] = req.content
        seen["ct"] = req.headers["content-type"]
        return httpx.Response(200, json=ANSWER)

    c = BackendClient("http://b/", token="tok", transport=httpx.MockTransport(handler))
    res = c.ask(b"\xff\xd8jpeg", "", "identify", "", audio=b"RIFFwav", audio_name="voice.wav", speech_format="both", want_speech=True)
    assert seen["url"] == "http://b/v1/ask"
    body = seen["body"]
    assert b'name="want_morse"\r\n\r\nfalse' in body                 # Morse is opt-in now
    assert b'name="speech_format"\r\n\r\nboth' in body
    assert b'name="want_speech"\r\n\r\ntrue' in body
    assert b'filename="voice.wav"' in body and b"audio/wav" in body
    assert b'filename="ring.jpg"' in body
    assert res.session_id == "s1" and res.speech_adpcm == ADPCM

    seen.clear()
    c.ask(None, "hello", "chat", "s1", audio=ADPCM, audio_name="voice.adpcm")
    assert b'name="want_speech"' not in seen["body"]                   # None = let the server decide
    assert b"audio/x-mcring-adpcm" in seen["body"]
    assert b'filename="ring.jpg"' not in seen["body"]


def test_speech_and_transcribe():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/speech":
            j = json.loads(req.content)
            assert j == {"text": "hi", "voice": "", "format": "adpcm16k"}
            return httpx.Response(200, content=ADPCM, headers={"content-type": "audio/x-mcring-adpcm"})
        if req.url.path == "/v1/transcribe":
            assert b'filename="q.m4a"' in req.content and b"audio/mp4" in req.content
            return httpx.Response(200, json={"text": "what is this", "provider": "openai", "model": "m", "audio_format": "m4a", "language": "en", "latency_ms": 5})
        return httpx.Response(404)

    c = BackendClient("http://b", transport=httpx.MockTransport(handler))
    assert c.speech("hi", fmt="adpcm16k") == ADPCM
    assert c.transcribe(b"m4a", "q.m4a")["text"] == "what is this"
    assert audio_mime_for("x.m4a") == "audio/mp4" and audio_mime_for("x.adpcm") == "audio/x-mcring-adpcm"
