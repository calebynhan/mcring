from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCRING_", env_file=".env", extra="ignore")

    # ---- the brain -----------------------------------------------------------
    provider: str = "anthropic"                 # anthropic | openai
    anthropic_model: str = "claude-opus-5-5"
    anthropic_fallbacks: bool = True            # server-side refusal fallbacks (Claude API only)
    anthropic_effort: str = "medium"            # low | medium | high
    openai_model: str = "gpt-4.1-mini"

    # ---- the voice out (answers are read aloud) ------------------------------
    # "none": the phone speaks with its own TTS engine. "openai": server-side speech, returned as
    # mp3 (phone/headphones) and/or 16 kHz mcring ADPCM (streamed by the phone to the ring speaker).
    tts_provider: str = "none"                  # none | openai
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "alloy"
    max_speech_chars: int = 1500                # longer answers are cut before synthesis

    # ---- the voice in (the wearer's question) --------------------------------
    stt_provider: str = "openai"                # openai | local | none
    stt_model: str = "gpt-4o-mini-transcribe"
    whisper_model: str = "base.en"              # faster-whisper model for stt_provider=local
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # ---- misc ------------------------------------------------------------------
    api_token: str = ""
    max_image_edge: int = 1024
    session_ttl_s: int = 1800
    max_upload_bytes: int = 8 * 1024 * 1024

    @property
    def tts_enabled(self) -> bool:
        return self.tts_provider.strip().lower() not in ("", "none")

    @property
    def stt_enabled(self) -> bool:
        return self.stt_provider.strip().lower() not in ("", "none")


@lru_cache
def get_settings() -> Settings:
    return Settings()
