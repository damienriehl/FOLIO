"""OpenAI structured-review adapter with an injectable transport."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable

from .base import ProviderError, ProviderReceipt, ReviewRequest


class OpenAIAdapter:
    provider = "openai"

    def __init__(
        self, model: str, transport: Callable[[dict], dict] | None = None,
        *, reasoning: str = "high", max_output_tokens: int = 4096,
    ):
        self.model = model
        self.reasoning = reasoning
        self.max_output_tokens = max_output_tokens
        self._transport = transport or _responses_transport

    def assess(self, request: ReviewRequest) -> ProviderReceipt:
        if request.model != self.model:
            raise ProviderError("request model does not match pinned OpenAI route")
        payload = {
            "model": self.model,
            "reasoning": {"effort": self.reasoning},
            "max_output_tokens": self.max_output_tokens,
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
        usage = raw.get("usage") or {}
        return ProviderReceipt(
            self.provider, self.model, actual, request.request_id,
            tuple(responses),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )


def _responses_transport(payload: dict) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ProviderError("OPENAI_API_KEY is not configured")
    body = dict(payload)
    body["input"] = json.dumps(payload["input"], ensure_ascii=False)
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = json.load(response)
    except urllib.error.HTTPError as exc:
        raise ProviderError(
            f"OpenAI request failed with HTTP {exc.code}",
            transient=exc.code in {408, 409, 429} or exc.code >= 500,
        ) from exc
    except (OSError, ValueError) as exc:
        raise ProviderError(f"OpenAI request failed: {exc}", transient=True) from exc
    text = raw.get("output_text")
    if text is None:
        for item in raw.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text = content.get("text")
                    break
    try:
        responses = json.loads(text) if isinstance(text, str) else None
    except json.JSONDecodeError as exc:
        raise ProviderError("OpenAI returned invalid structured JSON") from exc
    return {
        "model": raw.get("model"), "responses": responses,
        "usage": raw.get("usage") or {},
    }
