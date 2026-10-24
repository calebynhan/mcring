"""HTTP client for backend/ (FastAPI): /v1/ask, /v1/transcribe, /v1/speech, /v1/health."""
from __future__ import annotations

import base64
import pathlib
from dataclasses import dataclass, field

import httpx

MODES = ("identify", "describe", "read_text", "translate", "chat", "custom")
SPEECH_FORMATS = ("mp3", "adpcm16k", "both")
AUDIO_MIMES = {"wav": "audio/wav", "m4a": "audio/mp4", "mp4": "audio/mp4", "mp3": "audio/mpeg", "ogg": "audio/ogg",
               "flac": "audio/flac", "webm": "audio/webm", "adpcm": "audio/x-mcring-adpcm", "caf": "audio/x-caf",
               "aac": "audio/aac"}


def audio_mime_for(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return AUDIO_MIMES.get(ext, "application/octet-stream")


@dataclass
class AskResult:
    answer: str
    speech_text: str
    subject: str
    confidence: float
    session_id: str
    follow_up: str | None = None
    warnings: list[str] = field(default_factory=list)
    mode: str = ""
    had_image: bool = False
    transcript: str | None = None
    transcript_error: str | None = None
    speech_mp3: bytes | None = None        # for the laptop speakers / headphones
    speech_adpcm: bytes | None = None      # 16 kHz mcring-ADPCM for the ring speaker
    speech_error: str | None = None
    # Legacy "silent pattern" (only when asked for with want_morse)
    short: str | None = None
    morse_units: list[int] = field(default_factory=list)
    morse_unit_ms: int = 80
    ring_packet: bytes | None = None
    provider: str = ""
    model: str = ""
    latency_ms: int = 0
    raw: dict = field(default_factory=dict)


def _b64(d: dict | None) -> bytes | None:
    if d and d.get("audio_b64"):
        return base64.b64decode(d["audio_b64"])
    return None


def parse_ask(j: dict) -> AskResult:
    m = j.get("morse") or {}
    answer = j.get("answer", "")
    follow_up = j.get("follow_up") or None
    speech_text = j.get("speech_text") or (f"{answer} {follow_up}".strip() if follow_up else answer)
    return AskResult(
        answer=answer, speech_text=speech_text, subject=j.get("subject", "") or "", confidence=float(j.get("confidence", 0) or 0),
        session_id=j.get("session_id", ""), follow_up=follow_up, warnings=list(j.get("warnings") or []),
        mode=j.get("mode", ""), had_image=bool(j.get("had_image", False)),
        transcript=j.get("transcript") or None, transcript_error=j.get("transcript_error") or None,
        speech_mp3=_b64(j.get("speech")), speech_adpcm=_b64(j.get("speech_adpcm")), speech_error=j.get("speech_error") or None,
        short=j.get("short") or (m.get("text") if m else None),
        morse_units=list(m.get("units", [])), morse_unit_ms=int(m.get("unit_ms", 80) or 80),
        ring_packet=base64.b64decode(m["ring_packet_b64"]) if m.get("ring_packet_b64") else None,
        provider=j.get("provider", ""), model=j.get("model", ""), latency_ms=int(j.get("latency_ms", 0) or 0), raw=j,
    )


class BackendClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 90.0, transport: httpx.BaseTransport | None = None):
        self.base = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.timeout = timeout
        self._http = httpx.Client(headers=self.headers, timeout=timeout, transport=transport)

    def health(self) -> dict:
        r = self._http.get(f"{self.base}/v1/health", timeout=10)
        r.raise_for_status()
        return r.json()

    def ask(self, image: bytes | None = None, question: str = "", mode: str = "identify", session_id: str = "",
            provider: str = "", *, audio: bytes | None = None, audio_name: str = "voice.adpcm", audio_mime: str = "",
            want_speech: bool | None = None, speech_format: str = "mp3", voice: str = "", language: str = "en",
            want_morse: bool = False, char_wpm: int = 15, overall_wpm: int = 8, channels: int = 3) -> AskResult:
        """One turn. `audio` is a WAV/m4a/mp3 clip or raw ring ADPCM (name it `voice.adpcm`). No image = chat
        (or the session's previous photo). want_speech=None lets the server decide (TTS when configured)."""
        files = {}
        if image is not None:
            files["image"] = ("ring.jpg", image, "image/jpeg")
        if audio is not None:
            files["audio"] = (audio_name, audio, audio_mime or audio_mime_for(audio_name))
        data = {
            "question": question, "mode": mode, "session_id": session_id, "provider": provider, "language": language,
            "speech_format": speech_format, "voice": voice, "want_morse": "true" if want_morse else "false",
            "morse_char_wpm": str(char_wpm), "morse_overall_wpm": str(overall_wpm), "morse_channels": str(channels),
        }
        if want_speech is not None:
            data["want_speech"] = "true" if want_speech else "false"
        r = self._http.post(f"{self.base}/v1/ask", data=data, files=files or None)
        r.raise_for_status()
        return parse_ask(r.json())

    def transcribe(self, audio: bytes, audio_name: str = "voice.wav", audio_mime: str = "", language: str = "") -> dict:
        r = self._http.post(f"{self.base}/v1/transcribe", data={"language": language},
                            files={"audio": (audio_name, audio, audio_mime or audio_mime_for(audio_name))})
        r.raise_for_status()
        return r.json()

    def speech(self, text: str, voice: str = "", fmt: str = "mp3") -> bytes:
        """Text → audio bytes: mp3, or 16 kHz mcring-ADPCM (fmt='adpcm16k') for the ring speaker."""
        r = self._http.post(f"{self.base}/v1/speech", json={"text": text, "voice": voice, "format": fmt},
                            headers={"Accept": "audio/*"})
        r.raise_for_status()
        return r.content


def save_capture(data: bytes, directory: pathlib.Path, suffix: str = ".jpg") -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    import time

    p = directory / time.strftime(f"capture-%Y%m%d-%H%M%S{suffix}")
    p.write_bytes(data)
    return p
