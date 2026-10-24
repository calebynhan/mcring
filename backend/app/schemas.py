from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# "chat" = voice/text conversation with no photo (also what any mode degrades to when no photo exists).
Mode = Literal["identify", "describe", "read_text", "translate", "chat", "custom"]
MODES: tuple[str, ...] = ("identify", "describe", "read_text", "translate", "chat", "custom")

SpeechFormat = Literal["mp3", "adpcm16k"]
SPEECH_FORMATS: tuple[str, ...] = ("mp3", "adpcm16k")
ASK_SPEECH_FORMATS: tuple[str, ...] = ("mp3", "adpcm16k", "both")


class LLMAnswer(BaseModel):
    """Structured output we ask the model for (mirrors llm.ANSWER_SCHEMA sent to the API)."""

    answer: str = Field(description="The spoken answer: 1-3 short sentences written to be read aloud. "
                                    "No lists, markdown, URLs or emoji; numbers as words where natural.")
    subject: str = Field(default="", description="Main subject identified, e.g. 'Digitalis purpurea (foxglove)'. Empty if none.")
    confidence: float = Field(default=0.5, ge=0, le=1, description="0-1 confidence in the identification/answer.")
    warnings: list[str] = Field(default_factory=list, description="Safety-relevant notes (toxic, allergenic, hot, ...). Empty if none.")
    follow_up: str = Field(default="", description="Optional single short follow-up offer, e.g. 'Want to know if it is edible?'. "
                                                   "Empty if none. Read aloud after the answer.")

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.5
        return min(1.0, max(0.0, f))

    @field_validator("follow_up", "subject", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        return "" if v is None else v

    @property
    def speech_text(self) -> str:
        """Exactly what the phone (or ring) should say."""
        fu = self.follow_up.strip()
        return f"{self.answer.strip()} {fu}".strip() if fu else self.answer.strip()


class MorseOut(BaseModel):
    text: str
    unit_ms: int
    units: list[int]
    duration_ms: int
    ring_packet_b64: str
    char_wpm: int
    overall_wpm: int


class SpeechOut(BaseModel):
    format: str                       # mp3 | adpcm16k
    mime: str                         # audio/mpeg | audio/x-mcring-adpcm
    audio_b64: str
    voice: str
    sample_rate: int | None = None    # adpcm16k: 16000
    blocks: int | None = None         # adpcm16k: number of 132-byte / 256-sample blocks
    duration_ms: int | None = None    # adpcm16k: blocks * 16 ms


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class AskResponse(BaseModel):
    id: str
    session_id: str
    answer: str
    speech_text: str                  # answer (+ follow_up): the text to read aloud
    follow_up: str | None = None
    subject: str = ""
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    mode: str                         # effective mode ("chat" when no photo was involved)
    had_image: bool
    transcript: str | None = None     # transcription of an uploaded voice question
    transcript_error: str | None = None
    speech: SpeechOut | None = None         # mp3 for phone/headphones
    speech_adpcm: SpeechOut | None = None   # 16 kHz mcring ADPCM for the ring speaker
    speech_error: str | None = None
    # Optional "silent pattern" output (off by default). `short` is the pattern text (== morse.text).
    short: str | None = None
    morse: MorseOut | None = None
    provider: str
    model: str
    latency_ms: int
    usage: Usage = Field(default_factory=Usage)
    fallback_model: str | None = None


class MorseRequest(BaseModel):
    text: str
    char_wpm: int = 15
    overall_wpm: int = 8
    channels: int = 3


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str = ""
    format: SpeechFormat = "mp3"


class TranscribeResponse(BaseModel):
    text: str
    provider: str
    model: str
    audio_format: str                 # wav | m4a | mp3 | ogg | flac | webm | adpcm
    language: str | None = None
    latency_ms: int


class HealthResponse(BaseModel):
    status: str
    version: str
    provider: str
    model: str
    tts: str
    stt: str
    speech_default: bool              # whether /v1/ask returns speech unless told otherwise
    speech_formats: list[str] = Field(default_factory=lambda: list(SPEECH_FORMATS))
