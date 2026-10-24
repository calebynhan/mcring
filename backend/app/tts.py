"""Optional server-side speech synthesis. Default is 'none' (the phone speaks the answer)."""
from __future__ import annotations

import base64
import logging

from .config import Settings
from .schemas import SpeechOut

log = logging.getLogger("mcring.tts")


def synthesize(text: str, settings: Settings) -> SpeechOut | None:
    prov = settings.tts_provider.lower()
    if prov in ("", "none"):
        return None
    if prov == "openai":
        from openai import OpenAI

        client = OpenAI()
        resp = client.audio.speech.create(model="gpt-4o-mini-tts", voice=settings.tts_voice, input=text, response_format="mp3")
        audio = resp.content if hasattr(resp, "content") else resp.read()
        return SpeechOut(mime="audio/mpeg", audio_b64=base64.b64encode(audio).decode(), voice=settings.tts_voice)
    log.warning("unknown TTS provider %s", prov)
    return None


def transcribe(audio_bytes: bytes, filename: str, settings: Settings) -> str | None:
    """Transcribe a voice question. Uses OpenAI Whisper-class models when an OPENAI key is present."""
    try:
        from openai import OpenAI
    except ImportError:
        return None
    import os

    if not os.environ.get("OPENAI_API_KEY"):
        return None
    client = OpenAI()
    resp = client.audio.transcriptions.create(model="gpt-4o-mini-transcribe", file=(filename, audio_bytes))
    return getattr(resp, "text", None)
