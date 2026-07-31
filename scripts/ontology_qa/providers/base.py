"""Provider-neutral request and receipt contract."""

from __future__ import annotations

from dataclasses import dataclass
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
    def __init__(self, message: str, *, transient: bool = False):
        super().__init__(message)
        self.transient = transient


class ProviderAdapter(Protocol):
    provider: str
    model: str

    def assess(self, request: ReviewRequest) -> ProviderReceipt: ...
