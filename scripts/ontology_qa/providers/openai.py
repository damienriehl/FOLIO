"""OpenAI structured-review adapter with an injectable transport."""

from __future__ import annotations

from typing import Callable

from .base import ProviderError, ProviderReceipt, ReviewRequest


class OpenAIAdapter:
    provider = "openai"

    def __init__(self, model: str, transport: Callable[[dict], dict]):
        self.model = model
        self._transport = transport

    def assess(self, request: ReviewRequest) -> ProviderReceipt:
        if request.model != self.model:
            raise ProviderError("request model does not match pinned OpenAI route")
        payload = {
            "model": self.model,
            "instructions": request.prompt,
            "input": list(request.records),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ontology_reviews",
                    "strict": True,
                    "schema": {
                        "type": "array",
                        "items": request.schema,
                    },
                }
            },
        }
        raw = self._transport(payload)
        actual = raw.get("model")
        if actual != self.model:
            raise ProviderError(f"OpenAI served unpinned model: {actual}")
        responses = raw.get("responses")
        if not isinstance(responses, list):
            raise ProviderError("OpenAI response omitted structured responses")
        return ProviderReceipt(self.provider, self.model, actual, request.request_id, tuple(responses))
