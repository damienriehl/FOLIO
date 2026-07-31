"""Immutable provider caching and fail-closed live-review budgets."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .providers.base import ProviderAdapter, ProviderReceipt, ReviewRequest
from .records import canonical_json, content_hash


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class ReviewBudget:
    maximum_requests: int
    maximum_input_tokens: int
    maximum_output_tokens: int
    maximum_cost_usd: float
    pricing: dict[str, dict[str, float]]
    requests: int = 0
    input_tokens: int = 0
    reserved_output_tokens: int = 0
    projected_cost_usd: float = 0.0

    def reserve(
        self, *, route: str, input_tokens: int, maximum_output_tokens: int
    ) -> None:
        prices = self.pricing[route]
        projected = (
            input_tokens * float(prices["input_per_million"])
            + maximum_output_tokens * float(prices["output_per_million"])
        ) / 1_000_000
        if self.requests + 1 > self.maximum_requests:
            raise BudgetExceeded("provider request ceiling exhausted")
        if self.input_tokens + input_tokens > self.maximum_input_tokens:
            raise BudgetExceeded("input-token ceiling exhausted")
        if (
            self.reserved_output_tokens + maximum_output_tokens
            > self.maximum_output_tokens
        ):
            raise BudgetExceeded("output-token ceiling exhausted")
        if self.projected_cost_usd + projected > self.maximum_cost_usd:
            raise BudgetExceeded("cost ceiling exhausted")
        self.requests += 1
        self.input_tokens += input_tokens
        self.reserved_output_tokens += maximum_output_tokens
        self.projected_cost_usd += projected

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


class ImmutableReviewCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self, key: str) -> ProviderReceipt | None:
        path = self.root / f"{key}.json"
        if not path.exists():
            return None
        raw = path.read_bytes()
        value = json.loads(raw)
        if raw != canonical_json(value) + b"\n":
            raise ValueError("cached receipt is not canonical")
        body = dict(value)
        claimed = body.pop("cache_hash", None)
        if content_hash(canonical_json(body)) != claimed:
            raise ValueError("cached receipt hash mismatch")
        if body["request_id"] != key:
            raise ValueError("cached receipt request identity mismatch")
        return ProviderReceipt(
            provider=body["provider"],
            requested_model=body["requested_model"],
            actual_model=body["actual_model"],
            request_id=body["request_id"],
            responses=tuple(body["responses"]),
            retry_count=int(body["retry_count"]),
            input_tokens=int(body["input_tokens"]),
            output_tokens=int(body["output_tokens"]),
            cache_hit=True,
        )

    def publish(self, receipt: ProviderReceipt) -> None:
        body = {
            **asdict(receipt),
            "responses": list(receipt.responses),
            "cache_hit": False,
        }
        value = {"cache_hash": content_hash(canonical_json(body)), **body}
        data = canonical_json(value) + b"\n"
        path = self.root / f"{receipt.request_id}.json"
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError("immutable cache entry collision")
            return
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)


def request_identity(
    *,
    provider: str,
    model: str,
    reasoning: str,
    prompt: str,
    records: list[dict[str, Any]],
    schema: dict[str, Any],
    qualification_hash: str,
    policy_hash: str,
    candidate_hash: str,
) -> str:
    return content_hash(canonical_json({
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "prompt_hash": content_hash(prompt),
        "record_hash": content_hash(canonical_json(records)),
        "schema_hash": content_hash(canonical_json(schema)),
        "qualification_hash": qualification_hash,
        "policy_hash": policy_hash,
        "candidate_hash": candidate_hash,
    }))


class ReviewExecutor:
    def __init__(self, *, cache: ImmutableReviewCache, budget: ReviewBudget):
        self.cache = cache
        self.budget = budget
        self.cache_hits = 0

    def assess(
        self, adapter: ProviderAdapter, request: ReviewRequest,
        *, validator: Callable[[ProviderReceipt], None] | None = None,
    ) -> ProviderReceipt:
        cached = self.cache.load(request.request_id)
        if cached is not None:
            if (
                cached.provider != adapter.provider
                or cached.requested_model != adapter.model
                or cached.actual_model != adapter.model
            ):
                raise ValueError("cached receipt route mismatch")
            if validator is not None:
                validator(cached)
            self.cache_hits += 1
            return cached
        input_tokens = max(
            1,
            math.ceil(
                (
                    len(request.prompt.encode("utf-8"))
                    + len(canonical_json(list(request.records)))
                )
                / 4
            ),
        )
        maximum_output_tokens = int(
            getattr(adapter, "max_output_tokens", 4096)
        )
        self.budget.reserve(
            route=f"{adapter.provider}:{adapter.model}",
            input_tokens=input_tokens,
            maximum_output_tokens=maximum_output_tokens,
        )
        receipt = adapter.assess(request)
        if validator is not None:
            validator(receipt)
        self.cache.publish(receipt)
        return receipt
