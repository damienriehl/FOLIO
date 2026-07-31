#!/usr/bin/env python3
"""Run the protected, model-bearing ontology QA pipeline fail-closed."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, SKOS

from ontology_qa.delta import build_hydration_manifest
from ontology_qa.evals import (
    corpus_identity, evaluate_predictions, load_cases, load_model_policy,
)
from ontology_qa.providers.base import ProviderError, ReviewRequest
from ontology_qa.providers.google import GoogleAdapter
from ontology_qa.providers.openai import OpenAIAdapter
from ontology_qa.qualification import create_qualification
from ontology_qa.reconcile import reconcile
from ontology_qa.records import artifact_envelope, canonical_json, content_hash
from ontology_qa.reporting import ArtifactBundle, build_release_report
from ontology_qa.sampling import evaluate_surveillance, select_surveillance_sample
from ontology_qa.validators import (
    TARGET_PREDICATES, compare_validation_results, validate_ontology,
)

ROOT = Path(__file__).parents[1]
FAMILY = {
    str(SKOS.definition): "definition",
    str(SKOS.example): "example",
}


def _adapter(route: dict[str, Any]):
    if route["provider"] == "openai":
        return OpenAIAdapter(route["model"], reasoning=route["reasoning"])
    if route["provider"] == "google":
        return GoogleAdapter(route["model"], reasoning=route["reasoning"])
    raise ValueError(f"unsupported provider: {route['provider']}")


def _prompt() -> str:
    paths = [
        ROOT / "qa/ontology/prompts/definition-review.md",
        ROOT / "qa/ontology/prompts/example-review.md",
        ROOT / "qa/ontology/prompts/translation-review.md",
    ]
    return "\n\n".join(path.read_text(encoding="utf-8") for path in paths)


def _call(adapter, records: list[dict[str, Any]], schema: dict[str, Any]) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    validator = Draft202012Validator(schema)
    for offset in range(0, len(records), 50):
        batch = records[offset:offset + 50]
        request_id = content_hash(canonical_json({
            "model": adapter.model,
            "record_ids": [item["record_id"] for item in batch],
        }))
        request = ReviewRequest(
            request_id=request_id, model=adapter.model, prompt=_prompt(),
            records=tuple(batch), schema=schema,
            context_hash=content_hash(canonical_json(batch)),
        )
        receipt = None
        for attempt in range(3):
            try:
                receipt = adapter.assess(request)
                break
            except ProviderError as exc:
                if not exc.transient or attempt == 2:
                    raise
        if receipt is None:
            raise ValueError("provider returned no receipt")
        for response in receipt.responses:
            validator.validate(response)
        expected = sorted(item["record_id"] for item in batch)
        actual = sorted(item["record_id"] for item in receipt.responses)
        if expected != actual or len(actual) != len(set(actual)):
            raise ValueError("provider response IDs do not exactly match request")
        responses.extend(receipt.responses)
    return responses


def _qualify(
    adapter, role: str, policy: dict[str, Any], schema: dict[str, Any],
    policy_hash: str,
) -> dict[str, Any]:
    paths = [
        ROOT / "qa/ontology/evals/cases.jsonl",
        ROOT / "qa/ontology/evals/held-out.jsonl",
    ]
    cases = [case for path in paths for case in load_cases(path)]
    id_map = {content_hash(case["case_id"]): case["case_id"] for case in cases}
    records = [
        {
            "record_id": hashed,
            "family": case["family"],
            "locale": case["locale"],
            "annotation": case["input"],
        }
        for hashed, case_id in id_map.items()
        for case in cases if case["case_id"] == case_id
    ]
    responses = _call(adapter, records, schema)
    predictions = {
        id_map[item["record_id"]]: item["verdict"] for item in responses
    }
    metrics = evaluate_predictions(
        cases, predictions,
        minimum_cases_per_slice=int(policy["minimum_scored_cases_per_slice"]),
    )
    now = datetime.now(UTC)
    route = next(
        value for value in policy["routes"].values()
        if value["provider"] == adapter.provider and value["model"] == adapter.model
    )
    return create_qualification(
        role=role, route_id=f"{adapter.provider}:{adapter.model}",
        provider=adapter.provider, requested_model=adapter.model,
        actual_model=adapter.model, reasoning=route["reasoning"],
        corpus_hash=corpus_identity(paths), prompt_hash=content_hash(_prompt()),
        schema_hash=content_hash(canonical_json(schema)), policy_hash=policy_hash,
        metrics=metrics, thresholds=policy["qualification"],
        qualified_at=now.isoformat().replace("+00:00", "Z"),
        valid_until=(now + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
    )


def _review_artifact(
    adapter, records, qualification, *, manifest, run_id, attempt_id,
    policy_hash, tool_hash, schema,
):
    if qualification["status"] != "qualified":
        raise ValueError(f"{qualification['role']} route failed qualification")
    responses = _call(adapter, records, schema)
    return artifact_envelope(
        payload={
            "provider": adapter.provider, "model": adapter.model,
            "actual_model": adapter.model,
            "qualification_hash": qualification["qualification_hash"],
            "responses": responses,
        },
        run_id=run_id, attempt_id=attempt_id,
        parent_hashes=[manifest["artifact_hash"], qualification["qualification_hash"]],
        baseline_hash=manifest["baseline_hash"],
        candidate_hash=manifest["candidate_hash"],
        policy_hash=policy_hash, tool_hash=tool_hash, status="complete",
    )


def _census_artifact(baseline: Path, candidate: Path, manifest, run_id, attempt_id,
                     policy_hash, tool_hash):
    kwargs = {
        "policy_path": ROOT / "qa/ontology/review-policy.yaml",
        "shapes_path": ROOT / "qa/ontology/shapes.ttl",
    }
    before = validate_ontology(baseline, **kwargs)
    after = validate_ontology(candidate, **kwargs)
    payload = compare_validation_results(before, after)
    blocking = payload["failures"]
    payload["legacy_failures"] = before["failures"]
    payload["candidate_failure_count"] = len(payload["all_candidate_failures"])
    return artifact_envelope(
        payload=payload, run_id=run_id, attempt_id=attempt_id,
        parent_hashes=[manifest["artifact_hash"]],
        baseline_hash=manifest["baseline_hash"], candidate_hash=manifest["candidate_hash"],
        policy_hash=policy_hash, tool_hash=tool_hash,
        status="complete" if not blocking else "failed",
    )


def _legacy_records(candidate: Path, changed_ids: set[str]) -> list[dict[str, Any]]:
    records = []
    graph = Graph().parse(candidate, format="xml")
    for subject, predicate, value in graph:
        if predicate not in TARGET_PREDICATES or not isinstance(subject, URIRef) or not isinstance(value, Literal):
            continue
        locale = (value.language or "en").lower()
        family = FAMILY.get(str(predicate))
        if family is None and predicate in {RDFS.label, SKOS.prefLabel, SKOS.altLabel, SKOS.hiddenLabel} and locale != "en":
            family = "translation"
        if family is None:
            continue
        record_id = content_hash(canonical_json({
            "subject": str(subject), "predicate": str(predicate),
            "lexical": str(value), "locale": locale,
        }))
        if record_id in changed_ids:
            continue
        records.append({
            "record_id": record_id, "family": family, "locale": locale,
            "risk_tier": "standard", "subject": str(subject),
            "predicate": str(predicate), "annotation": str(value),
        })
    return sorted(records, key=lambda item: item["record_id"])


def _changed_review_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    label_predicates = {
        str(RDFS.label), str(SKOS.prefLabel), str(SKOS.altLabel),
        str(SKOS.hiddenLabel),
    }
    for record in manifest["payload"]["records"]:
        value = record.get("after") or record.get("before")
        predicate = value["predicate"]
        locale = (value.get("language") or "en").lower()
        family = FAMILY.get(predicate)
        if predicate in label_predicates and locale != "en":
            family = "translation"
        if family is None:
            raise ValueError(
                f"changed record is outside qualified semantic families: {record['record_id']}"
            )
        records.append({**record, "family": family, "locale": locale})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--reviewed-sha", required=True)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.reviewed_sha):
        print("trusted ontology QA failed: reviewed SHA is not immutable", file=sys.stderr)
        return 1
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    attempt_id = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    try:
        model_policy_path = ROOT / "qa/ontology/model-policy.yaml"
        model_policy = load_model_policy(model_policy_path)
        review_policy = yaml.safe_load(
            (ROOT / "qa/ontology/review-policy.yaml").read_text(encoding="utf-8")
        )
        schema = json.loads(
            (ROOT / model_policy["review_schema"]).read_text(encoding="utf-8")
        )
        policy_hash = content_hash(
            model_policy_path.read_bytes()
            + (ROOT / "qa/ontology/review-policy.yaml").read_bytes()
        )
        tool_hash = content_hash(Path(__file__).read_bytes())
        manifest = build_hydration_manifest(
            args.baseline, args.candidate, run_id=run_id, attempt_id=attempt_id,
            policy_hash=policy_hash, tool_hash=tool_hash,
        )
        bundle = ArtifactBundle(args.bundle)
        bundle.publish_json("manifest", manifest)
        bundle.snapshot("baseline.owl", args.baseline)
        bundle.snapshot("candidate.owl", args.candidate)
        if manifest["payload"]["unrelated_semantic_drift"]:
            raise ValueError("candidate contains unrelated semantic drift")
        census = _census_artifact(
            args.baseline, args.candidate, manifest, run_id, attempt_id,
            policy_hash, tool_hash,
        )
        bundle.publish_json("census", census)
        if census["payload"]["failures"]:
            raise ValueError("candidate introduced deterministic failures")

        primary_adapter = _adapter(model_policy["routes"]["primary"])
        independent_adapter = _adapter(model_policy["routes"]["independent"])
        primary_q = _qualify(
            primary_adapter, "production-primary", model_policy, schema, policy_hash
        )
        independent_q = _qualify(
            independent_adapter, "production-independent", model_policy, schema, policy_hash
        )
        bundle.publish_qualification("primary_qualification", primary_q)
        bundle.publish_qualification("independent_qualification", independent_q)
        records = _changed_review_records(manifest)
        primary = _review_artifact(
            primary_adapter, records, primary_q, manifest=manifest, run_id=run_id,
            attempt_id=attempt_id, policy_hash=policy_hash, tool_hash=tool_hash,
            schema=schema,
        )
        independent = _review_artifact(
            independent_adapter, records, independent_q, manifest=manifest,
            run_id=run_id, attempt_id=attempt_id, policy_hash=policy_hash,
            tool_hash=tool_hash, schema=schema,
        )
        bundle.publish_json("primary", primary)
        bundle.publish_json("independent", independent)
        reconciliation = reconcile(
            [item["record_id"] for item in records],
            primary, independent,
            minimum_confidence=float(model_policy["minimum_confidence"]),
            expected_candidate_hash=manifest["candidate_hash"],
            expected_primary_qualification=primary_q["qualification_hash"],
            expected_independent_qualification=independent_q["qualification_hash"],
        )

        legacy = _legacy_records(
            args.candidate, {item["record_id"] for item in records}
        )
        sample = select_surveillance_sample(legacy, review_policy)
        selected = set(
            record_id for value in sample["strata"].values()
            for record_id in value["selected_ids"]
        )
        sample_records = [item for item in legacy if item["record_id"] in selected]
        legacy_primary = _review_artifact(
            primary_adapter, sample_records, primary_q, manifest=manifest,
            run_id=run_id, attempt_id=attempt_id, policy_hash=policy_hash,
            tool_hash=tool_hash, schema=schema,
        )
        legacy_independent = _review_artifact(
            independent_adapter, sample_records, independent_q, manifest=manifest,
            run_id=run_id, attempt_id=attempt_id, policy_hash=policy_hash,
            tool_hash=tool_hash, schema=schema,
        )
        legacy_reconciliation = reconcile(
            sorted(selected), legacy_primary, legacy_independent,
            minimum_confidence=float(model_policy["minimum_confidence"]),
            expected_candidate_hash=manifest["candidate_hash"],
            expected_primary_qualification=primary_q["qualification_hash"],
            expected_independent_qualification=independent_q["qualification_hash"],
        )
        results = {
            record_id: {"verdict": "pass" if state == "accepted" else "defect",
                        "defect_types": []}
            for record_id, state in legacy_reconciliation["records"].items()
        }
        surveillance_result = evaluate_surveillance(
            sample, legacy, results, review_policy
        )
        surveillance = artifact_envelope(
            payload=surveillance_result, run_id=run_id, attempt_id=attempt_id,
            parent_hashes=[manifest["artifact_hash"]],
            baseline_hash=manifest["baseline_hash"],
            candidate_hash=manifest["candidate_hash"],
            policy_hash=policy_hash, tool_hash=tool_hash,
            status="complete",
        )
        bundle.publish_json("surveillance", surveillance)
        report = build_release_report(
            manifest=manifest, census=census, primary=primary,
            independent=independent, primary_qualification=primary_q,
            independent_qualification=independent_q,
            reconciliation=reconciliation, surveillance=surveillance,
            run_id=run_id, attempt_id=attempt_id,
            policy_hash=policy_hash, tool_hash=tool_hash,
        )
        for name, artifact in (
            ("manifest", manifest), ("census", census), ("primary", primary),
            ("independent", independent), ("surveillance", surveillance),
            ("report", report),
        ):
            bundle.publish_json(name, artifact)
        bundle.publish_qualification("primary_qualification", primary_q)
        bundle.publish_qualification("independent_qualification", independent_q)
        bundle.snapshot("baseline.owl", args.baseline)
        bundle.snapshot("candidate.owl", args.candidate)
        bundle.publish_index(report)
        if report["payload"]["release_decision"] != "merge_gate_passed":
            raise ValueError("release decision is blocked")
        print(json.dumps({"release_decision": "merge_gate_passed",
                          "report_hash": report["artifact_hash"]}, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"trusted ontology QA failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
