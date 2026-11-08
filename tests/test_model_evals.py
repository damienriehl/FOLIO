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
    load_slice_controls,
    qualification_identity,
    score_qualification_rounds,
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
    assert result["scored_count"] == 14
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


def test_each_required_slice_has_independent_quality_metrics():
    cases = [
        {
            "case_id": "clean", "family": "translation", "locale": "ja-jp",
            "authority": "deterministic-gold", "expected_verdict": "pass",
        },
        {
            "case_id": "defect", "family": "translation", "locale": "ja-jp",
            "authority": "deterministic-gold", "expected_verdict": "defect",
        },
    ]
    result = evaluate_predictions(
        cases, {"clean": "pass", "defect": "pass"},
        minimum_cases_per_slice=2,
        required_slices={("translation", "ja-jp"), ("translation", "zh-cn")},
    )
    assert result["slice_metrics"] == [{
        "family": "translation", "locale": "ja-jp", "scored_count": 2,
        "missing_case_ids": [], "accuracy": 0.5, "defect_recall": 0.0,
        "false_accept_rate": 1.0,
    }]
    assert {
        "family": "translation", "locale": "zh-cn", "count": 0,
    } in result["unsupported_slices"]


def test_frozen_controls_cover_every_policy_slice():
    policy = load_model_policy(ROOT / "qa/ontology/model-policy.yaml")
    required = {
        (family, locale)
        for family, locales in policy["required_slices"].items()
        for locale in locales
    }
    controls = load_slice_controls(
        ROOT / "qa/ontology/evals/slice-controls.json", required
    )
    assert len(controls) == len(required) * 3
    assert {
        (case["family"], case["locale"]) for case in controls
    } == required
    assert {
        case["expected_verdict"] for case in controls
    } == {"pass", "defect"}


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


@pytest.mark.parametrize("prediction", ["abstain", "pass", "invalid-replacement", None])
def test_only_actual_defect_predictions_count_as_detection(prediction):
    cases = [{
        "case_id": "defect", "family": "definition", "locale": "en",
        "authority": "deterministic-gold", "expected_verdict": "defect",
    }]
    predictions = {} if prediction is None else {"defect": prediction}
    result = evaluate_predictions(cases, predictions, minimum_cases_per_slice=1)
    assert result["defect_recall"] == 0
    assert result["false_accept_rate"] == (1 if prediction == "pass" else 0)


def test_proposer_repeat_stability_includes_exact_replacement():
    case = {
        "case_id": "repair", "family": "definition", "locale": "en",
        "authority": "deterministic-gold", "expected_verdict": "defect",
        "expected_replacement": "correct",
    }
    record_id = content_hash("repair")
    rounds = [[{
        "record_id": record_id, "verdict": "defect",
        "proposed_replacement": replacement,
    }] for replacement in ("correct", "wrong")]
    result = score_qualification_rounds(
        [case], rounds, role="correction-proposer",
        minimum_cases_per_slice=1, required_slices={("definition", "en")},
    )
    assert result["repeat_stability"] is False
    assert result["round_metrics"][0]["defect_recall"] == 1
    assert result["round_metrics"][1]["defect_recall"] == 0


def test_duplicate_or_extra_round_responses_are_incomplete():
    case = {
        "case_id": "one", "family": "definition", "locale": "en",
        "authority": "deterministic-gold", "expected_verdict": "pass",
    }
    record_id = content_hash("one")
    response = {"record_id": record_id, "verdict": "pass"}
    result = score_qualification_rounds(
        [case], [[response, response], [response]], role="production-primary",
        minimum_cases_per_slice=1, required_slices={("definition", "en")},
    )
    assert result["round_metrics"][0]["response_set_complete"] is False
