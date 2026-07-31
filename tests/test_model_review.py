from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.model_review import run_blind_review
from ontology_qa.providers.google import GoogleAdapter
from ontology_qa.providers.openai import OpenAIAdapter
from ontology_qa.providers.base import ProviderError, ReviewRequest

ROOT = Path(__file__).parents[1]
SCHEMA = json.loads((ROOT / "schemas/ontology-review.schema.json").read_text())
RID = "a" * 64


def response(record_id=RID, verdict="pass", confidence=0.99):
    return {
        "record_id": record_id, "verdict": verdict, "confidence": confidence,
        "defect_types": [], "evidence_spans": [],
        "preserved_propositions": ["meaning preserved"], "rationale": "supported",
        "proposed_replacement": None,
    }


def invoke(adapter, records=None, candidate_hash="candidate"):
    return run_blind_review(
        adapter, records=records or [{"record_id": RID}], prompt="rubric", schema=SCHEMA,
        context_hash="context", qualification_hash="q" * 64, run_id="run",
        attempt_id="attempt", baseline_hash="baseline", candidate_hash=candidate_hash,
        policy_hash="policy", tool_hash="tool",
    )


def test_provider_adapters_receive_identical_blind_inputs():
    seen = []
    def transport(payload):
        seen.append(payload)
        return {"model": payload["model"], "responses": [response()]}
    left = invoke(OpenAIAdapter("gpt-5.6-sol", transport))
    right = invoke(GoogleAdapter("gemini-3.5-flash", transport))
    assert left["status"] == right["status"] == "complete"
    assert seen[0]["input"] == seen[1]["contents"]
    assert "responses" not in seen[0]["input"][0]


def test_omitted_or_invented_ids_fail_completeness():
    adapter = OpenAIAdapter("gpt-5.6-sol", lambda payload: {
        "model": payload["model"], "responses": [response("b" * 64)]
    })
    assert invoke(adapter)["status"] == "incomplete"


def test_unpinned_model_fails_without_substitution():
    adapter = OpenAIAdapter("gpt-5.6-sol", lambda payload: {
        "model": "alias-latest", "responses": [response()]
    })
    result = invoke(adapter)
    assert result["status"] == "incomplete"
    assert "unpinned" in result["payload"]["error"]


def test_transient_failure_retries_same_immutable_request():
    calls = []
    def transport(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise ProviderError("rate limited", transient=True)
        return {"model": payload["model"], "responses": [response()]}
    result = invoke(OpenAIAdapter("gpt-5.6-sol", transport))
    assert result["status"] == "complete"
    assert result["payload"]["retry_count"] == 1
    assert calls[0] == calls[1]


@pytest.mark.parametrize(
    ("adapter", "variable"),
    [
        (OpenAIAdapter("gpt-5.6-sol"), "OPENAI_API_KEY"),
        (GoogleAdapter("gemini-3.5-flash"), "GOOGLE_API_KEY"),
    ],
)
def test_default_live_transport_fails_closed_without_credentials(
    monkeypatch, adapter, variable
):
    monkeypatch.delenv(variable, raising=False)
    request = ReviewRequest(
        request_id="request", model=adapter.model, prompt="review",
        records=(), schema={"type": "object"}, context_hash="context",
    )
    with pytest.raises(ProviderError, match=variable):
        adapter.assess(request)
