from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from ontology_qa.execution import (
    BudgetExceeded, ImmutableReviewCache, ReviewBudget, ReviewExecutor,
    request_identity,
)
from ontology_qa.providers.base import ProviderReceipt, ReviewRequest


class Adapter:
    provider = "openai"
    model = "gpt-5.6-sol"
    max_output_tokens = 10

    def __init__(self):
        self.calls = 0

    def assess(self, request):
        self.calls += 1
        return ProviderReceipt(
            self.provider, self.model, self.model, request.request_id,
            ({"record_id": "a" * 64},), input_tokens=5, output_tokens=2,
        )


def budget(**changes):
    values = {
        "maximum_requests": 2,
        "maximum_input_tokens": 1000,
        "maximum_output_tokens": 100,
        "maximum_cost_usd": 1,
        "pricing": {
            "openai:gpt-5.6-sol": {
                "input_per_million": 5,
                "output_per_million": 30,
            }
        },
    }
    values.update(changes)
    return ReviewBudget(**values)


def request(key):
    return ReviewRequest(
        request_id=key, model="gpt-5.6-sol", prompt="review",
        records=({"record_id": "a" * 64},), schema={"type": "object"},
        context_hash="context",
    )


def test_immutable_cache_reuses_exact_request_without_spend(tmp_path):
    adapter = Adapter()
    executor = ReviewExecutor(
        cache=ImmutableReviewCache(tmp_path), budget=budget()
    )
    key = request_identity(
        provider=adapter.provider, model=adapter.model, reasoning="high",
        prompt="review", records=[{"record_id": "a" * 64}],
        schema={"type": "object"}, qualification_hash="q",
        policy_hash="p", candidate_hash="c",
    )
    assert executor.assess(adapter, request(key)).cache_hit is False
    assert executor.assess(adapter, request(key)).cache_hit is True
    assert adapter.calls == 1
    assert executor.budget.requests == 1


def test_budget_exhaustion_fails_before_provider_call(tmp_path):
    adapter = Adapter()
    executor = ReviewExecutor(
        cache=ImmutableReviewCache(tmp_path),
        budget=budget(maximum_cost_usd=0),
    )
    with pytest.raises(BudgetExceeded, match="cost"):
        executor.assess(adapter, request("b" * 64))
    assert adapter.calls == 0


def test_candidate_change_invalidates_request_identity():
    values = dict(
        provider="openai", model="gpt-5.6-sol", reasoning="high",
        prompt="review", records=[{"record_id": "a" * 64}],
        schema={"type": "object"}, qualification_hash="q", policy_hash="p",
    )
    assert request_identity(**values, candidate_hash="first") != request_identity(
        **values, candidate_hash="second"
    )
