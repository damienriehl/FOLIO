from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.evals import (
    corpus_identity,
    evaluate_predictions,
    load_cases,
    load_model_policy,
    qualification_identity,
)
from ontology_qa.records import content_hash

ROOT = Path(__file__).parents[1]
CASES = ROOT / "qa/ontology/evals/cases.jsonl"


def test_authority_tiers_and_challenges_are_preserved():
    cases = load_cases(CASES)
    predictions = {
        case["case_id"]: case["expected_verdict"]
        for case in cases
        if case["expected_verdict"] is not None
    }
    result = evaluate_predictions(cases, predictions, minimum_cases_per_slice=2)
    assert result["scored_count"] == 10
    assert result["challenge_count"] == 1
    assert result["accuracy"] == 1


def test_any_bound_input_change_invalidates_qualification(tmp_path):
    source = tmp_path / "prompt.md"
    source.write_text("first", encoding="utf-8")
    first = qualification_identity(
        model="m", provider="p", reasoning="high",
        corpus_hash=corpus_identity([CASES]), prompt_hash=content_hash(source.read_bytes()),
        schema_hash="schema", policy_hash="policy",
    )
    source.write_text("second", encoding="utf-8")
    second = qualification_identity(
        model="m", provider="p", reasoning="high",
        corpus_hash=corpus_identity([CASES]), prompt_hash=content_hash(source.read_bytes()),
        schema_hash="schema", policy_hash="policy",
    )
    assert first != second


def test_instruction_literal_remains_data():
    case = next(case for case in load_cases(CASES) if case["case_id"] == "gold-injection-001")
    assert "Ignore prior instructions" in case["input"]["candidate"]
    assert case["expected_defect_types"] == ["prompt_injection"]


def test_underrepresented_slice_is_unsupported():
    cases = load_cases(CASES)
    predictions = {
        case["case_id"]: case["expected_verdict"]
        for case in cases if case["expected_verdict"] is not None
    }
    result = evaluate_predictions(cases, predictions, minimum_cases_per_slice=2)
    assert {"family": "definition", "locale": "en", "count": 4} not in result["unsupported_slices"]
    assert result["unsupported_slices"]


def test_model_consensus_cannot_create_gold(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps({
        "case_id": "bad", "family": "definition", "locale": "en",
        "authority": "deterministic-gold", "source_kind": "model-consensus",
        "source_ref": "models", "input": {}, "expected_verdict": "pass",
        "expected_defect_types": []
    }) + "\n")
    with pytest.raises(ValueError, match="model consensus"):
        load_cases(path)


def test_policy_pins_two_non_claude_routes():
    policy = load_model_policy(ROOT / "qa/ontology/model-policy.yaml")
    assert policy["routes"]["primary"]["provider"] == "openai"
    assert policy["routes"]["independent"]["provider"] == "google"
    assert set(policy["forbidden_providers"]) == {"anthropic", "claude"}
