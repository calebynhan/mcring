import base64
import json

import pytest
from fastapi.testclient import TestClient

from app import llm, main
from app.schemas import LLMAnswer


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls = []

    def ask(self, image_bytes, media_type, question, history):
        self.calls.append({"question": question, "history": list(history), "media_type": media_type, "n": len(image_bytes)})
        if "edible" in question.lower():
            ans = LLMAnswer(answer="No, foxglove is poisonous.", short="N TOXIC", subject="Digitalis purpurea", confidence=0.9, warnings=["toxic"])
        else:
            ans = LLMAnswer(answer="That's a foxglove, Digitalis purpurea. All parts are toxic.", short="Foxglove, toxic!", subject="Digitalis purpurea", confidence=0.86, warnings=["toxic if ingested"])
        return llm.LLMResult(answer=ans, provider=self.name, model=self.model, input_tokens=1200, output_tokens=80)


@pytest.fixture
def client(monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(main, "get_provider", lambda name, settings: fake)
    c = TestClient(main.app)
    c.fake = fake
    return c


def test_health(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ask_returns_morse_and_packet(client, jpeg_bytes):
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")}, data={"question": "what is this?"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["subject"] == "Digitalis purpurea"
    assert j["short"] == "FOXGLOVE TOXIC"            # normalised for Morse
    m = j["morse"]
    assert m["unit_ms"] == 80 and m["units"][0] == 1   # F starts with a dot
    pkt = base64.b64decode(m["ring_packet_b64"])
    assert pkt[0] == 0x14 and pkt[1] == 80 and pkt[2] == 3
    assert int.from_bytes(pkt[3:5], "little") == len(m["units"])
    assert list(pkt[5:]) == m["units"]
    assert j["usage"]["input_tokens"] == 1200
    assert client.fake.calls[0]["media_type"] == "image/jpeg"
    assert "Identify" in client.fake.calls[0]["question"] and "what is this" in client.fake.calls[0]["question"]


def test_followup_uses_session_and_history(client, jpeg_bytes):
    r1 = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")})
    sid = r1.json()["session_id"]
    r2 = client.post("/v1/ask", data={"session_id": sid, "question": "is it edible?", "mode": "custom"})
    assert r2.status_code == 200, r2.text
    j = r2.json()
    assert j["session_id"] == sid
    assert j["short"] == "N TOXIC"
    call = client.fake.calls[1]
    assert call["question"].startswith("(About the previous photo.)")
    assert len(call["history"]) == 1
    assert json.loads(call["history"][0]["answer_json"])["subject"] == "Digitalis purpurea"


def test_requires_image_without_session(client):
    r = client.post("/v1/ask", data={"question": "hi"})
    assert r.status_code == 400


def test_rejects_garbage_image(client):
    r = client.post("/v1/ask", files={"image": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400


def test_big_png_is_downscaled_and_jpeg(client, big_png_bytes):
    r = client.post("/v1/ask", files={"image": ("big.png", big_png_bytes, "image/png")})
    assert r.status_code == 200
    call = client.fake.calls[0]
    assert call["media_type"] == "image/jpeg"
    assert call["n"] < len(big_png_bytes)


def test_morse_endpoint(client):
    r = client.post("/v1/morse", json={"text": "sos", "char_wpm": 20, "overall_wpm": 20})
    j = r.json()
    assert j["units"] == [1, 1, 1, 1, 1, 3, 3, 1, 3, 1, 3, 3, 1, 1, 1, 1, 1]
    assert j["unit_ms"] == 60 and j["duration_ms"] == 27 * 60


def test_refusal_maps_to_safe_answer(client, jpeg_bytes, monkeypatch):
    class Refusing:
        def ask(self, *a, **k):
            raise llm.ModelRefused()
    monkeypatch.setattr(main, "get_provider", lambda name, settings: Refusing())
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["short"] == "? NO ANSWER"


def test_provider_error_status(client, jpeg_bytes, monkeypatch):
    class Broken:
        def ask(self, *a, **k):
            raise llm.ProviderError("upstream down", status=503, retryable=True)
    monkeypatch.setattr(main, "get_provider", lambda name, settings: Broken())
    r = client.post("/v1/ask", files={"image": ("ring.jpg", jpeg_bytes, "image/jpeg")})
    assert r.status_code == 503 and r.json()["retryable"] is True


def test_token_required(monkeypatch, jpeg_bytes):
    from app.config import Settings, get_settings
    monkeypatch.setattr(main, "get_provider", lambda name, settings: FakeProvider())
    main.app.dependency_overrides[get_settings] = lambda: Settings(api_token="secret")
    try:
        c = TestClient(main.app)
        assert c.post("/v1/morse", json={"text": "e"}).status_code == 401
        assert c.post("/v1/morse", json={"text": "e"}, headers={"Authorization": "Bearer secret"}).status_code == 200
    finally:
        main.app.dependency_overrides.clear()
