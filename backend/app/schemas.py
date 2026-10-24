from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["identify", "describe", "read_text", "translate", "custom"]


class LLMAnswer(BaseModel):
    """Structured output we ask the model for (also the JSON schema sent to the API)."""

    answer: str = Field(description="Spoken answer: 1-3 short sentences, plain language, no markdown.")
    short: str = Field(
        description=(
            "Morse-friendly answer: at most 6 words and 32 characters, UPPERCASE A-Z 0-9 and spaces only, "
            "nouns first, no articles or filler, digits for numbers. Prefix with '? ' if confidence < 0.6."
        )
    )
    subject: str = Field(description="The main subject identified, e.g. 'Digitalis purpurea (foxglove)'. Empty if none.")
    confidence: float = Field(ge=0, le=1, description="0-1 confidence in the identification/answer.")
    warnings: list[str] = Field(default_factory=list, description="Safety-relevant notes (toxic, allergenic, hot, etc.). Empty if none.")


class MorseOut(BaseModel):
    text: str
    unit_ms: int
    units: list[int]
    duration_ms: int
    ring_packet_b64: str
    char_wpm: int
    overall_wpm: int


class SpeechOut(BaseModel):
    mime: str
    audio_b64: str
    voice: str


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class AskResponse(BaseModel):
    id: str
    session_id: str
    answer: str
    short: str
    subject: str = ""
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    morse: MorseOut | None = None
    speech: SpeechOut | None = None
    transcript: str | None = None
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


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    tts: str
