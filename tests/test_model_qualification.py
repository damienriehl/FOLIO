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
