"""Google Gemini structured-review adapter with an injectable transport."""

from __future__ import annotations

from typing import Callable

from .base import ProviderError, ProviderReceipt, ReviewRequest


class GoogleAdapter:
    provider = "google"

    def __init__(self, model: str, transport: Callable[[dict], dict]):
        self.model = model
        self._transport = transport

    def assess(self, request: ReviewRequest) -> ProviderReceipt:
        if request.model != self.model:
            raise ProviderError("request model does not match pinned Google route")
        payload = {
            "model": self.model,
            "system_instruction": request.prompt,
            "contents": list(request.records),
            "generation_config": {
                "response_mime_type": "application/json",
                "response_json_schema": {"type": "array", "items": request.schema},
            },
        }
        raw = self._transport(payload)
        actual = raw.get("model")
        if actual != self.model:
            raise ProviderError(f"Google served unpinned model: {actual}")
        responses = raw.get("responses")
        if not isinstance(responses, list):
            raise ProviderError("Google response omitted structured responses")
        return ProviderReceipt(self.provider, self.model, actual, request.request_id, tuple(responses))
