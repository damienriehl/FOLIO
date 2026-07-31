"""Provider-neutral request and receipt contract."""

from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Any, Protocol


@dataclass(frozen=True)
class ReviewRequest:
    request_id: str
    model: str
    prompt: str
    records: tuple[dict[str, Any], ...]
    schema: dict[str, Any]
    context_hash: str


@dataclass(frozen=True)
class ProviderReceipt:
    provider: str
    requested_model: str
    actual_model: str
    request_id: str
    responses: tuple[dict[str, Any], ...]
    retry_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hit: bool = False


class ProviderError(RuntimeError):
    def __init__(
        self, message: str, *, transient: bool = False,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message)
        self.transient = transient
        self.retry_after_seconds = retry_after_seconds


def wait_before_retry(error: ProviderError, attempt: int) -> None:
    """Apply bounded exponential backoff with jitter and Retry-After."""
    delay = min(30.0, 2.0 ** attempt) + random.uniform(0.0, 0.5)
    if error.retry_after_seconds is not None:
        delay = max(delay, min(120.0, error.retry_after_seconds))
    time.sleep(delay)


class ProviderAdapter(Protocol):
    provider: str
    model: str

    def assess(self, request: ReviewRequest) -> ProviderReceipt: ...
