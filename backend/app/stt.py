"""Speech-to-text: the wearer's spoken question.

Accepted uploads: WAV, m4a/mp4 (phone recordings), mp3/ogg/flac/webm, or a raw mcring ADPCM clip
from the ring mic (16 kHz, 132-byte blocks; converted to WAV here with mcring_core.adpcm).

Providers (MCRING_STT_PROVIDER):
  openai  gpt-4o-mini-transcribe (needs OPENAI_API_KEY); decodes every container itself.
  local   faster-whisper, optional dependency (`pip install faster-whisper`), model MCRING_WHISPER_MODEL
          (default base.en). It decodes compressed audio (m4a, mp3, ...) through PyAV, which ships with
          its own ffmpeg libraries - no system ffmpeg needed. Imported lazily; a clear 501 if missing.
  none    /v1/transcribe and voice uploads answer 501.
"""
from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass

from mcring_core import adpcm as adpcm_codec

from . import audio
from .config import Settings
from .errors import ProviderError, map_openai_error

log = logging.getLogger("mcring.stt")


@dataclass
class Transcript:
    text: str
    provider: str
    model: str
    audio_format: str
    language: str | None = None


def _lang_code(language: str | None) -> str | None:
    """'en-US' -> 'en'; anything that is not a 2/3-letter code -> None (let the model detect)."""
    if not language:
        return None
    code = language.strip().replace("_", "-").split("-")[0].lower()
    return code if 2 <= len(code) <= 3 and code.isalpha() else None


# ---------------------------------------------------------------------------
# Providers. Interface: name, model, transcribe(audio_bytes, filename, language) -> str
# ---------------------------------------------------------------------------
class OpenAISTT:
    name = "openai"

    def __init__(self, settings: Settings):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ProviderError("openai package not installed (pip install openai)", status=501) from e
        if not os.environ.get("OPENAI_API_KEY"):
            raise ProviderError("MCRING_STT_PROVIDER=openai needs OPENAI_API_KEY (or set MCRING_STT_PROVIDER=local)",
                                status=501)
        self.client = OpenAI()
        self.model = settings.stt_model

    def transcribe(self, data: bytes, filename: str, language: str | None) -> str:
        kwargs = {"language": language} if language else {}
        try:
            resp = self.client.audio.transcriptions.create(model=self.model, file=(filename, data), **kwargs)
        except Exception as e:  # noqa: BLE001
            raise map_openai_error(e, "openai transcription error") from e
        return (getattr(resp, "text", None) or "").strip()


class LocalWhisperSTT:
    name = "local"

    def __init__(self, settings: Settings):
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise ProviderError("local speech-to-text needs the optional dependency faster-whisper "
                                "(pip install faster-whisper, or pip install -e '.[local-stt]' in backend/)",
                                status=501) from e
        self.model_name = settings.whisper_model
        self.model = self.model_name
        log.info("loading faster-whisper %s on %s/%s", self.model_name, settings.whisper_device, settings.whisper_compute_type)
        self._model = WhisperModel(self.model_name, device=settings.whisper_device, compute_type=settings.whisper_compute_type)

    def transcribe(self, data: bytes, filename: str, language: str | None) -> str:
        lang = "en" if self.model_name.endswith(".en") else language
        try:
            segments, _info = self._model.transcribe(io.BytesIO(data), language=lang, beam_size=1, vad_filter=True)
            return " ".join(seg.text.strip() for seg in segments).strip()
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"local transcription failed: {e}", status=500) from e


_STT: dict[str, object] = {}


def get_stt_provider(settings: Settings):
    name = settings.stt_provider.strip().lower()
    if name in ("", "none"):
        raise ProviderError("no speech-to-text provider configured on the server (set MCRING_STT_PROVIDER=openai or local)",
                            status=501)
    if name not in _STT:
        if name == "openai":
            _STT[name] = OpenAISTT(settings)
        elif name == "local":
            _STT[name] = LocalWhisperSTT(settings)
        else:
            raise ProviderError(f"unknown STT provider {name!r}", status=501)
    return _STT[name]


def prepare_audio(data: bytes, filename: str = "", content_type: str = "") -> tuple[bytes, str, str]:
    """Sniff an upload; ring ADPCM becomes WAV. Returns (bytes, filename with the right extension, format)."""
    fmt = audio.sniff_audio(data, filename, content_type)
    if fmt == "adpcm":
        return adpcm_codec.adpcm_to_wav(data, audio.RING_RATE), "voice.wav", "adpcm"
    if fmt == "unknown":
        raise ProviderError("unrecognised audio format (send wav, m4a/mp4, mp3, ogg, flac, webm or raw mcring ADPCM)",
                            status=415)
    name = filename if (filename or "").lower().endswith(f".{fmt}") else f"voice.{fmt}"
    return data, name, fmt


def transcribe(data: bytes, filename: str, content_type: str, settings: Settings, language: str = "") -> Transcript:
    if not data:
        raise ProviderError("empty audio upload", status=400)
    body, name, fmt = prepare_audio(data, filename, content_type)
    prov = get_stt_provider(settings)
    lang = _lang_code(language)
    text = prov.transcribe(body, name, lang)
    return Transcript(text=text, provider=prov.name, model=prov.model, audio_format=fmt, language=lang)
