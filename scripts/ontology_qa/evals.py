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


def corpus_identity(paths: Iterable[str | Path]) -> str:
    members = []
    for raw_path in sorted(map(Path, paths), key=lambda value: str(value)):
        members.append({"path": str(raw_path), "hash": content_hash(raw_path.read_bytes())})
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
) -> dict[str, Any]:
    scored = [case for case in cases if case["authority"] in SCORED_TIERS]
    missing = sorted(case["case_id"] for case in scored if case["case_id"] not in predictions)
    correct = sum(predictions.get(case["case_id"]) == case["expected_verdict"] for case in scored)
    defects = [case for case in scored if case["expected_verdict"] == "defect"]
    false_accepts = sum(predictions.get(case["case_id"]) == "pass" for case in defects)
    slices: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for case in scored:
        slices[(case["family"], case["locale"])].append(case)
    unsupported = sorted(
        [
            {"family": family, "locale": locale, "count": len(items)}
            for (family, locale), items in slices.items()
            if len(items) < minimum_cases_per_slice
        ],
        key=lambda item: (item["family"], item["locale"]),
    )
    return {
        "scored_count": len(scored),
        "challenge_count": len(cases) - len(scored),
        "missing_case_ids": missing,
        "accuracy": correct / len(scored) if scored else 0.0,
        "defect_recall": (len(defects) - false_accepts) / len(defects) if defects else 0.0,
        "false_accept_rate": false_accepts / len(defects) if defects else 0.0,
        "unsupported_slices": unsupported,
    }


def load_model_policy(path: str | Path) -> dict[str, Any]:
    policy = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    serialized = json.dumps(policy).lower()
    if "claude" in serialized or "anthropic" in serialized:
        if set(policy.get("forbidden_providers", [])) < {"claude", "anthropic"}:
            raise ValueError("Claude or Anthropic may appear only in the forbidden provider list")
    return policy
