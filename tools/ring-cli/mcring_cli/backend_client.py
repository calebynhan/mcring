from __future__ import annotations

import base64
import pathlib
from dataclasses import dataclass

import httpx


@dataclass
class AskResult:
    answer: str
    short: str
    subject: str
    confidence: float
    warnings: list[str]
    morse_units: list[int]
    morse_unit_ms: int
    ring_packet: bytes | None
    speech_mp3: bytes | None
    session_id: str
    model: str
    latency_ms: int
    raw: dict


class BackendClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 90.0):
        self.base = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.timeout = timeout

    def health(self) -> dict:
        return httpx.get(f"{self.base}/v1/health", headers=self.headers, timeout=10).json()

    def ask(self, image: bytes | None, question: str = "", mode: str = "identify", session_id: str = "",
            provider: str = "", want_speech: bool = False, audio_adpcm: bytes | None = None,
            char_wpm: int = 15, overall_wpm: int = 8, channels: int = 3) -> AskResult:
        files = {}
        if image is not None:
            files["image"] = ("ring.jpg", image, "image/jpeg")
        if audio_adpcm is not None:
            files["audio"] = ("voice.adpcm", audio_adpcm, "audio/x-mcring-adpcm")
        data = {
            "question": question, "mode": mode, "session_id": session_id, "provider": provider,
            "want_morse": "true", "want_speech": "true" if want_speech else "false",
            "morse_char_wpm": str(char_wpm), "morse_overall_wpm": str(overall_wpm), "morse_channels": str(channels),
        }
        r = httpx.post(f"{self.base}/v1/ask", data=data, files=files or None, headers=self.headers, timeout=self.timeout)
        r.raise_for_status()
        j = r.json()
        m = j.get("morse") or {}
        sp = j.get("speech") or {}
        return AskResult(
            answer=j["answer"], short=j["short"], subject=j.get("subject", ""), confidence=j["confidence"],
            warnings=j.get("warnings", []),
            morse_units=m.get("units", []), morse_unit_ms=m.get("unit_ms", 80),
            ring_packet=base64.b64decode(m["ring_packet_b64"]) if m.get("ring_packet_b64") else None,
            speech_mp3=base64.b64decode(sp["audio_b64"]) if sp.get("audio_b64") else None,
            session_id=j["session_id"], model=j.get("model", ""), latency_ms=j.get("latency_ms", 0), raw=j,
        )


def save_capture(data: bytes, directory: pathlib.Path, suffix: str = ".jpg") -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    import time

    p = directory / time.strftime(f"capture-%Y%m%d-%H%M%S{suffix}")
    p.write_bytes(data)
    return p
