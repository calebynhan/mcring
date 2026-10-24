from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCRING_", env_file=".env", extra="ignore")

    provider: str = "anthropic"                 # anthropic | openai
    anthropic_model: str = "claude-opus-5-5"
    anthropic_fallbacks: bool = True            # server-side refusal fallbacks (Claude API only)
    anthropic_effort: str = "medium"            # low | medium | high
    openai_model: str = "gpt-4.1-mini"
    tts_provider: str = "none"                  # none | openai
    tts_voice: str = "alloy"
    api_token: str = ""
    max_image_edge: int = 1024
    session_ttl_s: int = 1800
    max_upload_bytes: int = 8 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
