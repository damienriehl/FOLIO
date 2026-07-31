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
from ontology_qa.context import build_graph_context
from ontology_qa.correction_evidence import verify_correction_lineage
from ontology_qa.debt import (
    closed_debt, load_debt, unresolved_debt_ids,
)
from ontology_qa.evals import (
    corpus_identity, evaluate_predictions, load_cases, load_model_policy,
    load_slice_controls,
)
from ontology_qa.execution import (
    BudgetExceeded, ImmutableReviewCache, ReviewBudget, ReviewExecutor,
    request_identity,
)
from ontology_qa.providers.base import (
    ProviderError, ReviewRequest, wait_before_retry,
)
from ontology_qa.providers.google import GoogleAdapter
from ontology_qa.providers.openai import OpenAIAdapter
from ontology_qa.qualification import create_qualification, validate_role_separation
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


def _adapter(route: dict[str, Any], *, maximum_output_tokens: int):
    if route["provider"] == "openai":
        return OpenAIAdapter(
            route["model"], reasoning=route["reasoning"],
            max_output_tokens=maximum_output_tokens,
        )
    if route["provider"] == "google":
        return GoogleAdapter(
            route["model"], reasoning=route["reasoning"],
            max_output_tokens=maximum_output_tokens,
        )
    raise ValueError(f"unsupported provider: {route['provider']}")


def _prompts() -> dict[str, str]:
    return {
        family: (
            ROOT / f"qa/ontology/prompts/{family}-review.md"
        ).read_text(encoding="utf-8")
        for family in ("definition", "example", "translation")
    }


def _all_prompts() -> dict[str, str]:
    return {
        **_prompts(),
        "correction-proposal": (
            ROOT / "qa/ontology/prompts/correction-proposal.md"
        ).read_text(encoding="utf-8"),
        "correction-verification": (
            ROOT / "qa/ontology/prompts/correction-verification.md"
        ).read_text(encoding="utf-8"),
    }


def _prompt_bundle_hash() -> str:
    return content_hash(canonical_json(_all_prompts()))


def _tool_manifest() -> dict[str, Any]:
    paths = [Path(__file__), *(ROOT / "scripts/ontology_qa").rglob("*.py")]
    members = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "hash": content_hash(path.read_bytes()),
        }
        for path in sorted(paths)
    ]
    body = {"members": members}
    return {"tool_hash": content_hash(canonical_json(body)), **body}


def _provider_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Project the closed schema onto provider-supported structural keywords."""
    unsupported = {"allOf", "if", "then", "else", "uniqueItems"}
    return {
        key: (
            _provider_schema(value) if isinstance(value, dict)
            else [
                _provider_schema(item) if isinstance(item, dict) else item
                for item in value
            ] if isinstance(value, list)
            else value
        )
        for key, value in schema.items()
        if key not in unsupported
    }


def _call(
    adapter,
    records: list[dict[str, Any]],
    schema: dict[str, Any],
    *,
    prompt: str,
    executor: ReviewExecutor,
    qualification_hash: str,
    policy_hash: str,
    candidate_hash: str,
    batch_size: int,
) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    validator = Draft202012Validator(schema)
    for offset in range(0, len(records), batch_size):
        batch = records[offset:offset + batch_size]
        request_schema = _provider_schema(schema)
        request_id = request_identity(
            provider=adapter.provider, model=adapter.model,
            reasoning=adapter.reasoning, prompt=prompt, records=batch,
            schema=request_schema, qualification_hash=qualification_hash,
            policy_hash=policy_hash, candidate_hash=candidate_hash,
        )
        request = ReviewRequest(
            request_id=request_id, model=adapter.model, prompt=prompt,
            records=tuple(batch), schema=request_schema,
            context_hash=content_hash(canonical_json(batch)),
        )
        expected = sorted(item["record_id"] for item in batch)

        def validate_receipt(receipt) -> None:
            records_by_id = {
                item["record_id"]: item for item in batch
            }
            for response in receipt.responses:
                validator.validate(response)
                supplied = canonical_json(
                    records_by_id.get(response["record_id"], {})
                ).decode("utf-8")
                if any(
                    span["quote"] not in supplied
                    for span in response["evidence_spans"]
                ):
                    raise ValueError(
                        "provider evidence is not grounded in request input"
                    )
            actual = sorted(
                item["record_id"] for item in receipt.responses
            )
            if expected != actual or len(actual) != len(set(actual)):
                raise ValueError(
                    "provider response IDs do not exactly match request"
                )

        receipt = None
        for attempt in range(3):
            try:
                receipt = executor.assess(
                    adapter, request, validator=validate_receipt
                )
                break
            except ProviderError as exc:
                if not exc.transient or attempt == 2:
                    raise
                wait_before_retry(exc, attempt)
        if receipt is None:
            raise ValueError("provider returned no receipt")
        responses.extend(receipt.responses)
    return responses


def _qualify(
    adapter, role: str, policy: dict[str, Any], schema: dict[str, Any],
    policy_hash: str, *, executor: ReviewExecutor,
) -> dict[str, Any]:
    paths = [
        ROOT / "qa/ontology/evals/cases.jsonl",
        ROOT / "qa/ontology/evals/held-out.jsonl",
        ROOT / "qa/ontology/evals/slice-controls.json",
    ]
    required_slices = {
        (family, locale)
        for family, locales in policy["required_slices"].items()
        for locale in locales
    }
    cases = [
        case
        for path in paths[:2]
        for case in load_cases(path)
    ] + load_slice_controls(paths[2], required_slices)
    id_map = {content_hash(case["case_id"]): case["case_id"] for case in cases}
    records = [
        {
            "record_id": hashed,
            "family": case["family"],
            "locale": case["locale"],
            "source": case["input"].get("source"),
            "annotation": case["input"].get("candidate"),
            "benchmark_input": case["input"],
        }
        for hashed, case_id in id_map.items()
        for case in cases if case["case_id"] == case_id
    ]
    response_rounds: list[list[dict[str, Any]]] = []
    prompts = _prompts()
    qualification_error = None
    try:
        for repeat in range(2):
            responses: list[dict[str, Any]] = []
            for family in ("definition", "example", "translation"):
                family_records = [
                    record for record in records if record["family"] == family
                ]
                responses.extend(
                    _call(
                        adapter, family_records, schema,
                        prompt=prompts[family], executor=executor,
                        qualification_hash=f"qualification-eval:{repeat + 1}",
                        policy_hash=policy_hash,
                        candidate_hash=corpus_identity(paths),
                        batch_size=int(policy["operations"]["batch_size"]),
                    )
                )
            response_rounds.append(responses)
    except (BudgetExceeded, ProviderError, ValueError) as exc:
        qualification_error = str(exc)
        response_rounds = [[], []]
    responses = response_rounds[0]
    predictions = {
        id_map[item["record_id"]]: item["verdict"] for item in responses
    }
    metrics = evaluate_predictions(
        cases, predictions,
        minimum_cases_per_slice=int(policy["minimum_scored_cases_per_slice"]),
        required_slices=required_slices,
    )
    metrics["repeat_stability"] = (
        len(response_rounds) == 2
        and {
            item["record_id"]: item["verdict"]
            for item in response_rounds[0]
        }
        == {
            item["record_id"]: item["verdict"]
            for item in response_rounds[1]
        }
    )
    metrics["qualification_error"] = qualification_error
    now = datetime.now(UTC)
    route = next(
        value for value in policy["routes"].values()
        if value["provider"] == adapter.provider and value["model"] == adapter.model
    )
    return create_qualification(
        role=role, route_id=f"{adapter.provider}:{adapter.model}",
        provider=adapter.provider, requested_model=adapter.model,
        actual_model=adapter.model, reasoning=route["reasoning"],
        corpus_hash=corpus_identity(paths), prompt_hash=_prompt_bundle_hash(),
        schema_hash=content_hash(canonical_json(schema)), policy_hash=policy_hash,
        metrics=metrics, thresholds=policy["qualification"],
        qualified_at=now.isoformat().replace("+00:00", "Z"),
        valid_until=(now + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
    )


def _review_artifact(
    adapter, records, qualification, *, manifest, run_id, attempt_id,
    policy_hash, tool_hash, schema, executor, batch_size,
):
    if qualification["status"] != "qualified":
        raise ValueError(f"{qualification['role']} route failed qualification")
    qualified_slices = {
        (item["family"], item["locale"])
        for item in qualification["metrics"].get("qualified_slices", [])
    }
    unsupported = sorted({
        (record["family"], record["locale"]) for record in records
        if (record["family"], record["locale"]) not in qualified_slices
    })
    if unsupported:
        raise ValueError(f"route is unqualified for semantic slices: {unsupported}")
    responses = []
    prompts = _prompts()
    try:
        for family in ("definition", "example", "translation"):
            family_records = [
                record for record in records if record["family"] == family
            ]
            responses.extend(
                _call(
                    adapter, family_records, schema, prompt=prompts[family],
                    executor=executor,
                    qualification_hash=qualification["qualification_hash"],
                    policy_hash=policy_hash,
                    candidate_hash=manifest["candidate_hash"],
                    batch_size=batch_size,
                )
            )
    except (BudgetExceeded, ProviderError, ValueError) as exc:
        return artifact_envelope(
            payload={
                "provider": adapter.provider, "model": adapter.model,
                "actual_model": adapter.model,
                "qualification_hash": qualification["qualification_hash"],
                "responses": [], "error": str(exc),
            },
            run_id=run_id, attempt_id=attempt_id,
            parent_hashes=[
                manifest["artifact_hash"], qualification["qualification_hash"]
            ],
            baseline_hash=manifest["baseline_hash"],
            candidate_hash=manifest["candidate_hash"],
            policy_hash=policy_hash, tool_hash=tool_hash,
            status="incomplete",
        )
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


def _legacy_records(
    graph: Graph,
    changed_ids: set[str],
) -> list[dict[str, Any]]:
    records = []
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
        raw_record = {
            "record_id": record_id, "family": family, "locale": locale,
            "risk_tier": "standard", "subject": str(subject),
            "predicate": str(predicate), "annotation": str(value),
            "after": {
                "subject": str(subject), "predicate": str(predicate),
                "object_kind": "literal", "language": value.language,
                "datatype": str(value.datatype) if value.datatype else None,
                "lexical": str(value),
            },
        }
        records.append(raw_record)
    return sorted(records, key=lambda item: item["record_id"])


def _unresolved_confirmed_debt(candidate: Path) -> list[str]:
    debt = load_debt(ROOT / "qa/ontology/confirmed-defects.json")
    return sorted(unresolved_debt_ids(candidate, debt))


def _closed_confirmed_debt(
    baseline: Path, candidate: Path
) -> tuple[list[str], set[str]]:
    return closed_debt(
        baseline, candidate,
        load_debt(ROOT / "qa/ontology/confirmed-defects.json"),
    )


def _surveillance_results(
    *,
    sample: dict[str, Any],
    legacy: list[dict[str, Any]],
    primary_adapter,
    independent_adapter,
    primary_q,
    independent_q,
    manifest,
    run_id,
    attempt_id,
    policy_hash,
    tool_hash,
    schema,
    model_policy,
    review_policy,
    executor,
    graph,
    risk_evidence,
) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = {}
    while True:
        selected = {
            record_id for value in sample["strata"].values()
            for record_id in value["selected_ids"]
        }
        pending = selected - set(results)
        records = []
        for item in legacy:
            if item["record_id"] not in pending:
                continue
            record = dict(item)
            record["context"] = build_graph_context(
                graph, record, risk_evidence=risk_evidence
            )
            records.append(record)
        if records:
            left = _review_artifact(
                primary_adapter, records, primary_q, manifest=manifest,
                run_id=run_id, attempt_id=attempt_id, policy_hash=policy_hash,
                tool_hash=tool_hash, schema=schema,
                executor=executor,
                batch_size=int(model_policy["operations"]["batch_size"]),
            )
            right = _review_artifact(
                independent_adapter, records, independent_q, manifest=manifest,
                run_id=run_id, attempt_id=attempt_id, policy_hash=policy_hash,
                tool_hash=tool_hash, schema=schema,
                executor=executor,
                batch_size=int(model_policy["operations"]["batch_size"]),
            )
            reconciled = reconcile(
                sorted(pending), left, right,
                minimum_confidence=float(model_policy["minimum_confidence"]),
                expected_candidate_hash=manifest["candidate_hash"],
                expected_primary_qualification=primary_q["qualification_hash"],
                expected_independent_qualification=independent_q["qualification_hash"],
            )
            for record_id, state in reconciled["records"].items():
                responses = [
                    item for artifact in (left, right)
                    for item in artifact["payload"]["responses"]
                    if item["record_id"] == record_id
                ]
                defect_types = sorted({
                    defect for response in responses
                    for defect in response.get("defect_types", [])
                })
                results[record_id] = {
                    "verdict": "pass" if state == "accepted" else "defect",
                    "defect_types": defect_types,
                }
        evaluated = evaluate_surveillance(sample, legacy, results, review_policy)
        expansions = {
            name: details["expansion_ids"]
            for name, details in evaluated["strata"].items()
            if details["expansion_ids"]
        }
        if not expansions:
            return evaluated
        expanded_count = len(selected) + sum(len(ids) for ids in expansions.values())
        maximum = int(review_policy["surveillance"]["maximum_review_records"])
        if expanded_count > maximum:
            raise ValueError("required surveillance census exceeds review budget")
        for name, ids in expansions.items():
            stratum = sample["strata"][name]
            stratum["selected_ids"] = sorted(set(stratum["selected_ids"]) | set(ids))
            stratum["sample_count"] = len(stratum["selected_ids"])
            stratum["census"] = True


def _changed_review_records(
    manifest: dict[str, Any],
    *,
    graph: Graph,
    risk_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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
        review_record = {**record, "family": family, "locale": locale}
        review_record["context"] = build_graph_context(
            graph, review_record, risk_evidence=risk_evidence
        )
        if (
            family == "translation"
            and review_record["context"]["source_annotation"] is None
        ):
            raise ValueError(
                f"translation lacks one unambiguous source annotation: "
                f"{record['record_id']}"
            )
        if (
            family == "example"
            and review_record["context"]["concept_definition"] is None
        ):
            raise ValueError(
                f"example lacks a concept definition: {record['record_id']}"
            )
        records.append(review_record)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--reviewed-sha", required=True)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--cache", type=Path, default=Path(".ontology-qa-cache"))
    parser.add_argument("--correction-ledger", type=Path)
    parser.add_argument("--correction-evidence", type=Path)
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
        tool_manifest = _tool_manifest()
        tool_hash = tool_manifest["tool_hash"]
        operations = model_policy["operations"]
        budget = ReviewBudget(
            maximum_requests=int(operations["maximum_requests"]),
            maximum_input_tokens=int(operations["maximum_input_tokens"]),
            maximum_output_tokens=int(operations["maximum_output_tokens"]),
            maximum_cost_usd=float(operations["maximum_cost_usd"]),
            pricing=operations["pricing"],
        )
        executor = ReviewExecutor(
            cache=ImmutableReviewCache(args.cache), budget=budget
        )
        manifest = build_hydration_manifest(
            args.baseline, args.candidate, run_id=run_id, attempt_id=attempt_id,
            policy_hash=policy_hash, tool_hash=tool_hash,
        )
        bundle = ArtifactBundle(args.bundle)
        bundle.publish_json("manifest", manifest)
        bundle.snapshot("baseline.owl", args.baseline)
        bundle.snapshot("candidate.owl", args.candidate)
        for destination, source in (
            ("model-policy.yaml", model_policy_path),
            ("review-policy.yaml", ROOT / "qa/ontology/review-policy.yaml"),
            ("review-schema.json", ROOT / model_policy["review_schema"]),
            ("eval-cases.jsonl", ROOT / "qa/ontology/evals/cases.jsonl"),
            ("eval-held-out.jsonl", ROOT / "qa/ontology/evals/held-out.jsonl"),
            ("eval-slice-controls.json", ROOT / "qa/ontology/evals/slice-controls.json"),
            ("prompt-definition.md", ROOT / "qa/ontology/prompts/definition-review.md"),
            ("prompt-example.md", ROOT / "qa/ontology/prompts/example-review.md"),
            ("prompt-translation.md", ROOT / "qa/ontology/prompts/translation-review.md"),
            ("prompt-correction-proposal.md", ROOT / "qa/ontology/prompts/correction-proposal.md"),
            ("prompt-correction-verification.md", ROOT / "qa/ontology/prompts/correction-verification.md"),
        ):
            bundle.snapshot(destination, source)
        tool_manifest_path = bundle.root / "tool-manifest.json"
        tool_manifest_bytes = canonical_json(tool_manifest) + b"\n"
        if tool_manifest_path.exists() and tool_manifest_path.read_bytes() != tool_manifest_bytes:
            raise FileExistsError("append-only tool manifest already exists")
        if not tool_manifest_path.exists():
            tool_manifest_path.write_bytes(tool_manifest_bytes)
        if manifest["payload"]["unrelated_semantic_drift"]:
            raise ValueError("candidate contains unrelated semantic drift")
        census = _census_artifact(
            args.baseline, args.candidate, manifest, run_id, attempt_id,
            policy_hash, tool_hash,
        )
        bundle.publish_json("census", census)
        if census["payload"]["failures"]:
            raise ValueError("candidate introduced deterministic failures")
        unresolved_debt = _unresolved_confirmed_debt(args.candidate)
        if unresolved_debt:
            raise ValueError(
                f"candidate retains {len(unresolved_debt)} confirmed open defects"
            )
        closed_debt, closed_roots = _closed_confirmed_debt(
            args.baseline, args.candidate
        )
        correction_lineage = None
        supplied_correction_artifacts = (
            args.correction_ledger is not None
            or args.correction_evidence is not None
        )
        if closed_debt and not (
            args.correction_ledger and args.correction_evidence
        ):
            raise ValueError(
                "candidate closes confirmed debt without correction evidence"
            )
        if supplied_correction_artifacts:
            if not (args.correction_ledger and args.correction_evidence):
                raise ValueError(
                    "correction ledger and evidence must be supplied together"
                )
            correction_lineage = verify_correction_lineage(
                source_path=args.baseline,
                candidate_path=args.candidate,
                ledger_path=args.correction_ledger,
                evidence_path=args.correction_evidence,
                schema_path=ROOT / "schemas/ontology-correction.schema.json",
                minimum_confidence=float(
                    model_policy["minimum_confidence"]
                ),
            )
            ledger_roots = {
                item["root_record_id"]
                for item in json.loads(
                    args.correction_ledger.read_text(encoding="utf-8")
                )
            }
            if ledger_roots != closed_roots:
                raise ValueError(
                    "correction ledger roots differ from closed confirmed debt"
                )
            bundle.snapshot(
                "correction-ledger.json", args.correction_ledger
            )
            bundle.snapshot(
                "correction-evidence.json", args.correction_evidence
            )

        maximum_output = int(operations["maximum_output_tokens_per_request"])
        role_routes = {
            "production-primary": "primary",
            "production-independent": "independent",
            "benchmark-adjudicator": "benchmark_adjudicator",
            "correction-proposer": "correction_proposer",
            "correction-verifier-1": "correction_verifier_1",
            "correction-verifier-2": "correction_verifier_2",
        }
        adapters = {
            role: _adapter(
                model_policy["routes"][route_name],
                maximum_output_tokens=maximum_output,
            )
            for role, route_name in role_routes.items()
        }
        qualifications = {
            role: _qualify(
                adapter, role, model_policy, schema, policy_hash,
                executor=executor,
            )
            for role, adapter in adapters.items()
        }
        validate_role_separation(list(qualifications.values()))
        rejected_roles = sorted(
            role for role, qualification in qualifications.items()
            if qualification["status"] != "qualified"
        )
        if rejected_roles:
            raise ValueError(f"model routes failed qualification: {rejected_roles}")
        for role, qualification in qualifications.items():
            bundle.publish_qualification(
                f"{role.replace('-', '_')}_qualification", qualification
            )
        primary_adapter = adapters["production-primary"]
        independent_adapter = adapters["production-independent"]
        primary_q = qualifications["production-primary"]
        independent_q = qualifications["production-independent"]
        candidate_graph = Graph().parse(args.candidate, format="xml")
        records = _changed_review_records(
            manifest,
            graph=candidate_graph,
            risk_evidence=census["payload"]["semantic_review_risks"],
        )
        primary = _review_artifact(
            primary_adapter, records, primary_q, manifest=manifest, run_id=run_id,
            attempt_id=attempt_id, policy_hash=policy_hash, tool_hash=tool_hash,
            schema=schema,
            executor=executor, batch_size=int(operations["batch_size"]),
        )
        independent = _review_artifact(
            independent_adapter, records, independent_q, manifest=manifest,
            run_id=run_id, attempt_id=attempt_id, policy_hash=policy_hash,
            tool_hash=tool_hash, schema=schema,
            executor=executor, batch_size=int(operations["batch_size"]),
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
            candidate_graph,
            {item["record_id"] for item in records},
        )
        sample = select_surveillance_sample(legacy, review_policy)
        surveillance_result = _surveillance_results(
            sample=sample, legacy=legacy, primary_adapter=primary_adapter,
            independent_adapter=independent_adapter, primary_q=primary_q,
            independent_q=independent_q, manifest=manifest, run_id=run_id,
            attempt_id=attempt_id, policy_hash=policy_hash, tool_hash=tool_hash,
            schema=schema, model_policy=model_policy,
            review_policy=review_policy,
            executor=executor,
            graph=candidate_graph,
            risk_evidence=census["payload"]["semantic_review_risks"],
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
            correction_lineage=correction_lineage,
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
