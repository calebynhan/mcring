"""Text-to-speech: answers read aloud.

Two output formats:
  mp3       for the phone (played through the user's own Bluetooth headphones / phone speaker)
  adpcm16k  16 kHz mono mcring IMA-ADPCM (132-byte blocks) the phone streams straight to the ring
            speaker over the AUDIO_OUT characteristic (AUDIO_START codec=2, AUDIO_DATA blocks)

Providers: MCRING_TTS_PROVIDER=openai (gpt-4o-mini-tts) | none. For adpcm16k we ask the provider
for raw PCM (OpenAI: 24 kHz 16-bit LE mono) and resample/encode ourselves - no mp3 decoding needed.
"""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass

from . import audio
from .config import Settings
from .errors import ProviderError, map_openai_error
from .schemas import SPEECH_FORMATS, SpeechOut

log = logging.getLogger("mcring.tts")


@dataclass
class SynthResult:
    data: bytes
    mime: str
    format: str
    voice: str
    provider: str
    model: str
    sample_rate: int | None = None
    blocks: int | None = None
    duration_ms: int | None = None

    def to_speech_out(self) -> SpeechOut:
        return SpeechOut(format=self.format, mime=self.mime, audio_b64=base64.b64encode(self.data).decode(),
                         voice=self.voice, sample_rate=self.sample_rate, blocks=self.blocks, duration_ms=self.duration_ms)

    def headers(self) -> dict[str, str]:
        h = {"X-Mcring-Format": self.format, "X-Mcring-Voice": self.voice, "X-Mcring-Provider": self.provider,
             "Cache-Control": "no-store"}
        if self.sample_rate:
            h["X-Mcring-Sample-Rate"] = str(self.sample_rate)
        if self.blocks is not None:
            h["X-Mcring-Blocks"] = str(self.blocks)
        if self.duration_ms is not None:
            h["X-Mcring-Duration-Ms"] = str(self.duration_ms)
        return h


# ---------------------------------------------------------------------------
# Providers. Interface: name, model, speak(text, voice, fmt) -> (bytes, mime) with fmt in {"mp3", "pcm"}.
# "pcm" is raw 16-bit little-endian mono; mime carries the rate: "audio/pcm;rate=24000". WAV is also accepted.
# ---------------------------------------------------------------------------
class OpenAITTS:
    name = "openai"

    def __init__(self, settings: Settings):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ProviderError("openai package not installed (pip install openai)", status=501) from e
        if not os.environ.get("OPENAI_API_KEY"):
            raise ProviderError("MCRING_TTS_PROVIDER=openai needs OPENAI_API_KEY", status=501)
        self.client = OpenAI()
        self.model = settings.tts_model

    def speak(self, text: str, voice: str, fmt: str) -> tuple[bytes, str]:
        response_format = "mp3" if fmt == "mp3" else "pcm"
        try:
            resp = self.client.audio.speech.create(model=self.model, voice=voice, input=text,
                                                   response_format=response_format)
        except Exception as e:  # noqa: BLE001
            raise map_openai_error(e, "openai tts error") from e
        data = resp.content if hasattr(resp, "content") else resp.read()
        return data, ("audio/mpeg" if fmt == "mp3" else "audio/pcm;rate=24000")


_TTS: dict[str, object] = {}


def get_tts_provider(settings: Settings):
    name = settings.tts_provider.strip().lower()
    if name in ("", "none"):
        raise ProviderError("no speech provider configured on the server (set MCRING_TTS_PROVIDER=openai); "
                            "the phone can speak the answer with its own TTS instead", status=501)
    if name not in _TTS:
        if name == "openai":
            _TTS[name] = OpenAITTS(settings)
        else:
            raise ProviderError(f"unknown TTS provider {name!r}", status=501)
    return _TTS[name]


def synthesize(text: str, settings: Settings, *, voice: str = "", fmt: str = "mp3") -> SynthResult:
    """Speak `text` in the requested format. Raises ProviderError (501 when no provider is configured)."""
    if fmt not in SPEECH_FORMATS:
        raise ProviderError(f"unknown speech format {fmt!r} (use {', '.join(SPEECH_FORMATS)})", status=400)
    text = " ".join(text.split())
    if not text:
        raise ProviderError("nothing to say", status=400)
    if len(text) > settings.max_speech_chars:
        log.warning("speech text truncated from %d to %d chars", len(text), settings.max_speech_chars)
        text = text[: settings.max_speech_chars].rsplit(" ", 1)[0]
    prov = get_tts_provider(settings)
    voice = voice.strip() or settings.tts_voice

    if fmt == "mp3":
        data, mime = prov.speak(text, voice, "mp3")
        return SynthResult(data=data, mime=mime, format="mp3", voice=voice, provider=prov.name, model=prov.model)

    data, mime = prov.speak(text, voice, "pcm")
    try:
        pcm, rate = audio.decode_to_pcm(data, mime)
    except ValueError as e:
        raise ProviderError(str(e), status=501) from e
    blob = audio.pcm_to_ring_adpcm(audio.resample(pcm, rate, audio.RING_RATE))
    return SynthResult(data=blob, mime="audio/x-mcring-adpcm", format="adpcm16k", voice=voice,
                       provider=prov.name, model=prov.model, sample_rate=audio.RING_RATE,
                       blocks=audio.adpcm_blocks(blob), duration_ms=audio.adpcm_duration_ms(blob))
