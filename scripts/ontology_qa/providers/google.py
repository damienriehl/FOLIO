"""Google Gemini structured-review adapter with an injectable transport."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from .base import ProviderError, ProviderReceipt, ReviewRequest


class GoogleAdapter:
    provider = "google"

    def __init__(
        self, model: str, transport: Callable[[dict], dict] | None = None,
        *, reasoning: str = "high", max_output_tokens: int = 4096,
    ):
        self.model = model
        self.reasoning = reasoning
        self.max_output_tokens = max_output_tokens
        self._transport = transport or _gemini_transport

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
                "thinking_config": (
                    {"thinking_budget": -1}
                    if self.model.startswith("gemini-2.5-")
                    else {"thinking_level": self.reasoning}
                ),
                "max_output_tokens": self.max_output_tokens,
            },
        }
        raw = self._transport(payload)
        actual = raw.get("model")
        if actual != self.model:
            raise ProviderError(f"Google served unpinned model: {actual}")
        responses = raw.get("responses")
        if not isinstance(responses, list):
            raise ProviderError("Google response omitted structured responses")
        usage = raw.get("usage") or {}
        return ProviderReceipt(
            self.provider, self.model, actual, request.request_id,
            tuple(responses),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )


def _gemini_transport(payload: dict) -> dict:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ProviderError("GOOGLE_API_KEY is not configured")
    model = payload["model"]
    config = payload["generation_config"]
    body = {
        "systemInstruction": {
            "parts": [{"text": payload["system_instruction"]}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": json.dumps(payload["contents"])}],
            }
        ],
        "generationConfig": {
            "responseMimeType": config["response_mime_type"],
            "responseJsonSchema": config["response_json_schema"],
            "thinkingConfig": (
                {
                    "thinkingBudget":
                    config["thinking_config"]["thinking_budget"]
                }
                if "thinking_budget" in config["thinking_config"]
                else {
                    "thinkingLevel":
                    config["thinking_config"]["thinking_level"].upper()
                }
            ),
            "maxOutputTokens": config["max_output_tokens"],
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model, safe='')}:generateContent"
    )
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = json.load(response)
    except urllib.error.HTTPError as exc:
        raise ProviderError(
            f"Google request failed with HTTP {exc.code}",
            transient=exc.code in {408, 409, 429} or exc.code >= 500,
        ) from exc
    except (OSError, ValueError) as exc:
        raise ProviderError(f"Google request failed: {exc}", transient=True) from exc
    try:
        text = raw["candidates"][0]["content"]["parts"][0]["text"]
        responses = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        candidate = (raw.get("candidates") or [{}])[0]
        reason = candidate.get("finishReason") or raw.get("promptFeedback")
        raise ProviderError(
            f"Google returned invalid structured JSON"
            + (f": {str(reason)[:500]}" if reason else "")
        ) from exc
    usage = raw.get("usageMetadata") or {}
    return {
        "model": raw.get("modelVersion", model), "responses": responses,
        "usage": {
            "input_tokens": usage.get("promptTokenCount", 0),
            "output_tokens": max(
                0,
                usage.get("totalTokenCount", 0)
                - usage.get("promptTokenCount", 0),
            ),
        },
    }
