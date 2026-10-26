"""Frozen ontology-review evaluation corpus and qualification identities."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml

from .records import canonical_json, content_hash

AUTHORITY_TIERS = {"deterministic-gold", "source-grounded-silver", "unscored-challenge"}
SCORED_TIERS = {"deterministic-gold", "source-grounded-silver"}


def qualification_records(
    cases: list[dict[str, Any]], *, correction_role: bool,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Build blind provider inputs and their opaque-to-case identifier map."""
    id_map = {content_hash(case["case_id"]): case["case_id"] for case in cases}
    by_id = {case["case_id"]: case for case in cases}
    records = []
    for record_id, case_id in id_map.items():
        case = by_id[case_id]
        record = {
            "record_id": record_id, "family": case["family"],
            "locale": case["locale"], "source": case["input"].get("source"),
            "annotation": case["input"].get("candidate"),
            "benchmark_input": case["input"],
        }
        if correction_role:
            original = case["input"]["candidate"]
            proposed = case.get("verification_candidate")
            record.update({
                "after": {
                    "subject": f"https://example.test/{record_id}",
                    "predicate": "http://www.w3.org/2004/02/skos/core#definition",
                    "object_kind": "literal", "language": case["locale"],
                    "datatype": None,
                    "lexical": proposed if proposed is not None else original,
                },
                "before": {
                    "subject": f"https://example.test/{record_id}",
                    "predicate": "http://www.w3.org/2004/02/skos/core#definition",
                    "object_kind": "literal", "language": case["locale"],
                    "datatype": None, "lexical": original,
                },
                "confirmed_defect": {
                    "class": case["expected_defect_types"][0],
                    "finding": case["source_ref"],
                },
            })
        records.append(record)
    return records, id_map


def correction_cases(
    controls: list[dict[str, Any]], *, role: str,
) -> list[dict[str, Any]]:
    """Derive evaluator-owned correction cases without exposing their oracle."""
    result = []
    for case in controls:
        if case["expected_verdict"] != "defect":
            continue
        base = {**case, "expected_replacement": case["input"]["source"]}
        if role == "correction-proposer":
            result.append(base)
        else:
            result.extend([
                {**base, "case_id": case["case_id"] + "-repaired",
                 "verification_candidate": base["expected_replacement"],
                 "expected_verdict": "pass"},
                {**base, "case_id": case["case_id"] + "-unrepaired",
                 "verification_candidate": case["input"]["candidate"],
                 "expected_verdict": "defect"},
            ])
    return result


def score_qualification_rounds(
    cases: list[dict[str, Any]], rounds: list[list[dict[str, Any]]],
    *, role: str, minimum_cases_per_slice: int,
    required_slices: set[tuple[str, str]],
) -> dict[str, Any]:
    """Score two complete rounds, keeping evaluator answers out of requests."""
    id_map = {content_hash(case["case_id"]): case["case_id"] for case in cases}
    by_case = {case["case_id"]: case for case in cases}
    round_metrics = []
    comparable = []
    for responses in rounds:
        ids = [item.get("record_id") for item in responses]
        complete = len(ids) == len(id_map) and set(ids) == set(id_map)
        predictions = {}
        comparison = {}
        if complete:
            for item in responses:
                case_id = id_map[item["record_id"]]
                verdict = item.get("verdict")
                if role == "correction-proposer":
                    replacement = item.get("proposed_replacement")
                    comparison[case_id] = (verdict, replacement)
                    if replacement != by_case[case_id]["expected_replacement"]:
                        verdict = "invalid-replacement"
                else:
                    comparison[case_id] = verdict
                predictions[case_id] = verdict
        metric = evaluate_predictions(
            cases, predictions,
            minimum_cases_per_slice=minimum_cases_per_slice,
            required_slices=required_slices,
        )
        if not complete:
            metric["response_set_complete"] = False
        else:
            metric["response_set_complete"] = True
        round_metrics.append(metric)
        comparable.append(comparison)
    first = dict(round_metrics[0]) if round_metrics else evaluate_predictions(
        cases, {}, minimum_cases_per_slice=minimum_cases_per_slice,
        required_slices=required_slices,
    )
    first["round_metrics"] = round_metrics
    first["repeat_stability"] = len(comparable) == 2 and comparable[0] == comparable[1]
    return first


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    cases = []
    seen = set()
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        case_id = case.get("case_id")
        if not case_id or case_id in seen:
            raise ValueError(f"duplicate or missing case_id at line {line_number}")
        seen.add(case_id)
        authority = case.get("authority")
        if authority not in AUTHORITY_TIERS:
            raise ValueError(f"invalid authority tier for {case_id}")
        if case.get("source_kind") == "model-consensus":
            raise ValueError(f"model consensus cannot establish benchmark authority: {case_id}")
        if authority == "source-grounded-silver" and (
            not case.get("source_ref") or not case.get("adjudication_hash")
        ):
            raise ValueError(f"source-grounded case lacks frozen provenance: {case_id}")
        if authority == "unscored-challenge" and case.get("expected_verdict") is not None:
            raise ValueError(f"challenge case cannot enter accuracy scoring: {case_id}")
        cases.append(case)
    return cases


def load_slice_controls(
    path: str | Path,
    required_slices: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Expand frozen language-neutral controls across required semantic slices."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("version") != 1 or not value.get("controls"):
        raise ValueError("invalid slice-control corpus")
    cases = []
    for family, locale in sorted(required_slices):
        for control in value["controls"]:
            cases.append({
                "case_id": (
                    f"gold-slice-{family}-{locale}-{control['id']}"
                ),
                "family": family,
                "locale": locale,
                "authority": "deterministic-gold",
                "source_kind": control["source_kind"],
                "source_ref": control["source_ref"],
                "input": {
                    "source": control.get(
                        "translation_source", control["source"]
                    ) if family == "translation" else control["source"],
                    "candidate": control.get(
                        "translation_candidate", control["candidate"]
                    ) if family == "translation" else control["candidate"],
                },
                "expected_verdict": control["expected_verdict"],
                "expected_defect_types": control["expected_defect_types"],
            })
    return cases


def corpus_identity(paths: Iterable[str | Path]) -> str:
    members = sorted(content_hash(Path(raw_path).read_bytes()) for raw_path in paths)
    return content_hash(canonical_json({"members": members}))


def qualification_identity(
    *,
    model: str,
    provider: str,
    reasoning: str,
    corpus_hash: str,
    prompt_hash: str,
    schema_hash: str,
    policy_hash: str,
) -> str:
    return content_hash(
        canonical_json(
            {
                "model": model,
                "provider": provider,
                "reasoning": reasoning,
                "corpus_hash": corpus_hash,
                "prompt_hash": prompt_hash,
                "schema_hash": schema_hash,
                "policy_hash": policy_hash,
            }
        )
    )


def evaluate_predictions(
    cases: list[dict[str, Any]],
    predictions: dict[str, str],
    *,
    minimum_cases_per_slice: int,
    required_slices: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    scored = [case for case in cases if case["authority"] in SCORED_TIERS]
    missing = sorted(case["case_id"] for case in scored if case["case_id"] not in predictions)
    correct = sum(predictions.get(case["case_id"]) == case["expected_verdict"] for case in scored)
    defects = [case for case in scored if case["expected_verdict"] == "defect"]
    false_accepts = sum(predictions.get(case["case_id"]) == "pass" for case in defects)
    detections = sum(predictions.get(case["case_id"]) == "defect" for case in defects)
    slices: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for case in scored:
        slices[(case["family"], case["locale"])].append(case)
    required = required_slices or set(slices)
    unsupported = sorted(
        [
            {
                "family": family, "locale": locale,
                "count": len(slices.get((family, locale), [])),
            }
            for family, locale in required
            if len(slices.get((family, locale), [])) < minimum_cases_per_slice
        ],
        key=lambda item: (item["family"], item["locale"]),
    )
    slice_metrics = []
    for (family, locale), items in sorted(slices.items()):
        if (family, locale) not in required:
            continue
        item_missing = sorted(
            item["case_id"] for item in items
            if item["case_id"] not in predictions
        )
        item_defects = [
            item for item in items if item["expected_verdict"] == "defect"
        ]
        item_false_accepts = sum(
            predictions.get(item["case_id"]) == "pass"
            for item in item_defects
        )
        item_detections = sum(
            predictions.get(item["case_id"]) == "defect"
            for item in item_defects
        )
        item_correct = sum(
            predictions.get(item["case_id"]) == item["expected_verdict"]
            for item in items
        )
        slice_metrics.append({
            "family": family, "locale": locale, "scored_count": len(items),
            "missing_case_ids": item_missing,
            "accuracy": item_correct / len(items) if items else 0.0,
            "defect_recall": (
                item_detections / len(item_defects)
                if item_defects else 0.0
            ),
            "false_accept_rate": (
                item_false_accepts / len(item_defects)
                if item_defects else 0.0
            ),
        })
    return {
        "scored_count": len(scored),
        "challenge_count": len(cases) - len(scored),
        "missing_case_ids": missing,
        "accuracy": correct / len(scored) if scored else 0.0,
        "defect_recall": detections / len(defects) if defects else 0.0,
        "false_accept_rate": false_accepts / len(defects) if defects else 0.0,
        "unsupported_slices": unsupported,
        "slice_metrics": slice_metrics,
    }


def load_model_policy(path: str | Path) -> dict[str, Any]:
    policy = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    serialized = json.dumps(policy).lower()
    if "claude" in serialized or "anthropic" in serialized:
        if set(policy.get("forbidden_providers", [])) < {"claude", "anthropic"}:
            raise ValueError("Claude or Anthropic may appear only in the forbidden provider list")
    return policy
