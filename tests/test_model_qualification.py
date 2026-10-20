from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.qualification import (
    create_qualification,
    require_current_qualification,
    validate_role_separation,
)
from ontology_qa.correction_pipeline import correction_response_schema
from ontology_qa.execution import (
    ImmutableReviewCache, ReviewBudget, ReviewExecutor,
)
from ontology_qa.evals import load_model_policy
from ontology_qa.providers.base import ProviderReceipt
from ontology_qa.records import canonical_json, content_hash
from run_trusted_ontology_qa import _qualify
import json

HASHES = {name: letter * 64 for name, letter in [
    ("corpus_hash", "a"), ("prompt_hash", "b"), ("schema_hash", "c"), ("policy_hash", "d")
]}
THRESHOLDS = {
    "minimum_accuracy": .9, "minimum_defect_recall": .95,
    "maximum_false_accept_rate": .02,
}
METRICS = {
    "accuracy": 1, "defect_recall": 1, "false_accept_rate": 0,
    "missing_case_ids": [], "unsupported_slices": [],
}


def qualification(role="production-primary", route="openai:gpt-5.6-sol", **changes):
    values = dict(
        role=role, route_id=route, provider=route.split(":")[0],
        requested_model=route.split(":")[1], actual_model=route.split(":")[1],
        reasoning="high", metrics=METRICS, thresholds=THRESHOLDS,
        qualified_at="2026-07-30T00:00:00Z", valid_until="2026-08-30T00:00:00Z",
        **HASHES,
    )
    values.update(changes)
    return create_qualification(**values)


def test_passing_route_publishes_content_addressed_artifact():
    artifact = qualification()
    assert artifact["status"] == "qualified"
    assert len(artifact["qualification_hash"]) == 64


def test_any_bound_change_invalidates_reuse():
    artifact = qualification()
    with pytest.raises(ValueError, match="binding mismatch"):
        require_current_qualification(
            artifact, expected_role="production-primary",
            expected_route_id="openai:gpt-5.6-sol",
            expected_binding_hashes={**HASHES, "prompt_hash": "e" * 64},
            now=datetime(2026, 8, 1, tzinfo=UTC),
        )


def test_benchmark_and_production_routes_must_be_disjoint():
    with pytest.raises(ValueError, match="benchmark"):
        validate_role_separation([
            qualification("production-primary", "openai:model"),
            qualification("benchmark-adjudicator", "openai:model"),
        ])


def test_proposer_and_verifiers_are_three_distinct_routes():
    with pytest.raises(ValueError, match="proposer"):
        validate_role_separation([
            qualification("correction-proposer", "openai:model"),
            qualification("correction-verifier-1", "openai:model"),
            qualification("correction-verifier-2", "google:model"),
        ])


def test_production_votes_must_use_different_providers():
    with pytest.raises(ValueError, match="production.*providers"):
        validate_role_separation([
            qualification("production-primary", "google:model-a"),
            qualification("production-independent", "google:model-b"),
        ])


def test_correction_verifiers_must_use_different_providers():
    with pytest.raises(ValueError, match="verifiers.*providers"):
        validate_role_separation([
            qualification("correction-verifier-1", "google:model-a"),
            qualification("correction-verifier-2", "google:model-b"),
        ])


def test_expired_or_mismatched_qualification_blocks():
    artifact = qualification()
    with pytest.raises(ValueError, match="expired"):
        require_current_qualification(
            artifact, expected_role="production-primary",
            expected_route_id="openai:gpt-5.6-sol",
            expected_binding_hashes=HASHES,
            now=datetime(2026, 9, 1, tzinfo=UTC),
        )


def test_model_alias_is_rejected():
    with pytest.raises(ValueError, match="served model"):
        qualification(actual_model="alias-latest")


def test_correction_proposer_qualifies_on_exact_repair_task(tmp_path):
    root = Path(__file__).parents[1]
    policy = load_model_policy(root / "qa/ontology/model-policy.yaml")
    schema = json.loads(
        (root / "schemas/ontology-review.schema.json").read_text()
    )

    class Adapter:
        provider = "openai"
        model = "gpt-5.6-sol"
        reasoning = "high"
        max_output_tokens = 1000

        def assess(self, request):
            responses = tuple({
                "record_id": record["record_id"],
                "verdict": "defect",
                "confidence": .99,
                "defect_types": ["number"],
                "evidence_spans": [{
                    "source": "annotation",
                    "quote": record["record_id"],
                }],
                "preserved_propositions": ["number restored"],
                "rationale": "Restores the frozen mutation.",
                "proposed_replacement": record["expected_replacement"],
            } for record in request.records)
            return ProviderReceipt(
                self.provider, self.model, self.model,
                request.request_id, responses,
            )

    executor = ReviewExecutor(
        cache=ImmutableReviewCache(tmp_path),
        budget=ReviewBudget(
            maximum_requests=100, maximum_input_tokens=1_000_000,
            maximum_output_tokens=1_000_000, maximum_cost_usd=100,
            pricing={
                "openai:gpt-5.6-sol": {
                    "input_per_million": 5,
                    "output_per_million": 30,
                },
            },
        ),
    )
    result = _qualify(
        Adapter(), "correction-proposer", policy, schema,
        "f" * 64, executor=executor,
    )
    expected_schema = correction_response_schema(schema, role="proposer")
    expected_prompt = (
        root / "qa/ontology/prompts/correction-proposal.md"
    ).read_text()
    assert result["status"] == "qualified"
    assert result["schema_hash"] == content_hash(
        canonical_json(expected_schema)
    )
    assert result["prompt_hash"] == content_hash(expected_prompt)
