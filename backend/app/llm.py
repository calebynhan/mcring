"""Answer providers (photo + question, or voice/text chat). Anthropic (Claude) is the default; OpenAI is optional."""
from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field

from .config import Settings
from .errors import ModelRefused, ProviderError, map_openai_error
from .prompts import SYSTEM_PROMPT
from .schemas import LLMAnswer

__all__ = ["ANSWER_SCHEMA", "LLMResult", "ModelRefused", "ProviderError", "get_provider"]

log = logging.getLogger("mcring.llm")


@dataclass
class LLMResult:
    answer: LLMAnswer
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    fallback_model: str | None = None
    raw_text: str = ""
    extra: dict = field(default_factory=dict)


# Sent verbatim as the structured-output schema (Anthropic output_config.format / OpenAI strict json_schema).
# Every key is required so both strict dialects accept it; optional values are empty strings/arrays.
# No numeric bounds: neither dialect supports minimum/maximum, LLMAnswer clamps confidence client-side.
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "description": "Spoken answer, 1-3 short sentences, read aloud as-is."},
        "subject": {"type": "string", "description": "Main subject identified, or empty."},
        "confidence": {"type": "number", "description": "0 to 1."},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "follow_up": {"type": "string", "description": "Optional one-line follow-up offer, or empty."},
    },
    "required": ["answer", "subject", "confidence", "warnings", "follow_up"],
    "additionalProperties": False,
}
ANSWER_KEYS = ", ".join(ANSWER_SCHEMA["required"])


def _image_block_anthropic(image_bytes: bytes, media_type: str) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.standard_b64encode(image_bytes).decode()}}


def _parse_answer(text: str) -> LLMAnswer:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to salvage a JSON object embedded in prose.
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ProviderError(f"model returned non-JSON output: {text[:200]!r}")
        data = json.loads(text[start : end + 1])
    return LLMAnswer.model_validate(data)


def _history_blocks(history: list[dict]) -> list[dict]:
    """Prior turns of a session as plain text (without re-sending old images)."""
    out: list[dict] = []
    for turn in history[-6:]:
        out.append({"role": "user", "content": turn["question"]})
        out.append({"role": "assistant", "content": turn["answer_json"]})
    return out


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings):
        import anthropic  # local import so the openai-only deployment doesn't need it

        self._anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model = settings.anthropic_model
        self.fallbacks = settings.anthropic_fallbacks
        self.effort = settings.anthropic_effort

    def ask(self, image_bytes: bytes | None, media_type: str | None, question: str, history: list[dict]) -> LLMResult:
        """One turn. `image_bytes` is None for a voice/text-only (chat) turn."""
        anthropic = self._anthropic
        content: list[dict] = []
        if image_bytes:
            content.append(_image_block_anthropic(image_bytes, media_type or "image/jpeg"))
        content.append({"type": "text", "text": question})
        messages = _history_blocks(history) + [{"role": "user", "content": content}]
        kwargs = dict(
            model=self.model,
            max_tokens=4096,  # adaptive thinking shares this budget; a voice answer itself is ~100 tokens
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            output_config={
                "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
                "effort": self.effort,
            },
        )
        t0 = time.time()
        try:
            if self.fallbacks:
                # Server-side refusal fallback: if a safety classifier declines, the API re-runs the
                # request on Anthropic's recommended substitute model inside the same call.
                resp = self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            else:
                resp = self.client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            raise ProviderError(f"anthropic rate limited: {e}", status=429, retryable=True) from e
        except anthropic.APIStatusError as e:
            raise ProviderError(f"anthropic error {e.status_code}: {e.message}", status=502,
                                retryable=e.status_code >= 500) from e
        except anthropic.APIConnectionError as e:
            raise ProviderError(f"anthropic connection error: {e}", status=503, retryable=True) from e
        log.info("anthropic %s answered in %.2fs", resp.model, time.time() - t0)

        if resp.stop_reason == "refusal":
            raise ModelRefused()

        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
        if not text:
            raise ProviderError("empty model response")
        answer = _parse_answer(text)
        served_by_fallback = any(
            getattr(it, "type", "") == "fallback_message" for it in (getattr(resp.usage, "iterations", None) or [])
        )
        return LLMResult(
            answer=answer, provider=self.name, model=resp.model,
            input_tokens=getattr(resp.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(resp.usage, "output_tokens", 0) or 0,
            fallback_model=resp.model if served_by_fallback and resp.model != self.model else None,
            raw_text=text,
        )


# ---------------------------------------------------------------------------
# OpenAI (optional, "ChatGPT" path)
# ---------------------------------------------------------------------------
class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings):
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise ProviderError("openai package not installed (pip install openai)", status=501) from e
        self.client = OpenAI()
        self.model = settings.openai_model

    def ask(self, image_bytes: bytes | None, media_type: str | None, question: str, history: list[dict]) -> LLMResult:
        messages = [{"role": "system", "content": SYSTEM_PROMPT + f"\nRespond with a single JSON object with keys {ANSWER_KEYS}."}]
        messages += _history_blocks(history)
        user_content: list[dict] = [{"type": "text", "text": question}]
        if image_bytes:
            data_url = f"data:{media_type or 'image/jpeg'};base64,{base64.standard_b64encode(image_bytes).decode()}"
            user_content.append({"type": "image_url", "image_url": {"url": data_url, "detail": "low"}})
        messages.append({"role": "user", "content": user_content})
        t0 = time.time()
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=600,
                response_format={"type": "json_schema", "json_schema": {"name": "mcring_answer", "schema": ANSWER_SCHEMA, "strict": True}},
            )
        except Exception as e:  # noqa: BLE001 - map any SDK error to a ProviderError
            raise map_openai_error(e, "openai error") from e
        log.info("openai %s answered in %.2fs", resp.model, time.time() - t0)
        choice = resp.choices[0]
        if getattr(choice, "finish_reason", "") == "content_filter":
            raise ModelRefused()
        text = choice.message.content or ""
        answer = _parse_answer(text)
        usage = getattr(resp, "usage", None)
        return LLMResult(
            answer=answer, provider=self.name, model=resp.model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            raw_text=text,
        )


_PROVIDERS: dict[str, object] = {}


def get_provider(name: str, settings: Settings):
    name = (name or settings.provider).lower()
    if name not in _PROVIDERS:
        if name == "anthropic":
            _PROVIDERS[name] = AnthropicProvider(settings)
        elif name == "openai":
            _PROVIDERS[name] = OpenAIProvider(settings)
        else:
            raise ProviderError(f"unknown provider {name!r}", status=400)
    return _PROVIDERS[name]
