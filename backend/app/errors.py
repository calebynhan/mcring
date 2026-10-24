"""Error types shared by the LLM, speech-to-text and text-to-speech providers."""
from __future__ import annotations


class ProviderError(RuntimeError):
    """An upstream/provider problem, mapped to an HTTP status by the API layer."""

    def __init__(self, message: str, status: int = 502, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class ModelRefused(ProviderError):
    def __init__(self, message: str = "the model declined this request"):
        super().__init__(message, status=422, retryable=False)


def map_openai_error(exc: Exception, what: str) -> ProviderError:
    """Turn any openai SDK exception into a ProviderError with a sensible status."""
    status = getattr(exc, "status_code", None) or 502
    if not isinstance(status, int) or status < 400:
        status = 502
    return ProviderError(f"{what}: {exc}", status=status, retryable=status in (408, 429, 500, 502, 503, 504))
