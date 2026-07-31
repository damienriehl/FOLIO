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
from tempfile import TemporaryDirectory
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, SKOS

from ontology_qa.delta import build_hydration_manifest
from ontology_qa.context import build_graph_context
from ontology_qa.correction_pipeline import (
    converge_correction, correction_response_schema,
)
from ontology_qa.corrections import apply_correction_batch
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
from ontology_qa.sampling import (
    build_legacy_records, evaluate_surveillance, select_surveillance_sample,
    surveillance_record_id,
)
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
    qualification_schema = schema
    qualification_prompt_hash = _prompt_bundle_hash()
    qualification_corpus_hash = corpus_identity(paths)
    correction_role = role in {
        "correction-proposer",
        "correction-verifier-1",
        "correction-verifier-2",
    }
    if correction_role:
        controls = [
            case for case in load_slice_controls(paths[2], required_slices)
            if case["expected_verdict"] == "defect"
        ]
        correction_cases = []
        for case in controls:
            expected_replacement = case["input"]["source"]
            base = {
                **case,
                "expected_replacement": expected_replacement,
            }
            if role == "correction-proposer":
                correction_cases.append(base)
            else:
                correction_cases.extend([
                    {
                        **base,
                        "case_id": case["case_id"] + "-repaired",
                        "verification_candidate": expected_replacement,
                        "expected_verdict": "pass",
                    },
                    {
                        **base,
                        "case_id": case["case_id"] + "-unrepaired",
                        "verification_candidate": case["input"]["candidate"],
                        "expected_verdict": "defect",
                    },
                ])
        cases = correction_cases
        schema_role = (
            "proposer" if role == "correction-proposer" else "verifier"
        )
        qualification_schema = correction_response_schema(
            schema, role=schema_role
        )
        prompt_name = (
            "correction-proposal"
            if role == "correction-proposer"
            else "correction-verification"
        )
        qualification_prompt = _all_prompts()[prompt_name]
        qualification_prompt_hash = content_hash(qualification_prompt)
        qualification_corpus_hash = content_hash(canonical_json(cases))
    id_map = {content_hash(case["case_id"]): case["case_id"] for case in cases}
    records = []
    for hashed, case_id in id_map.items():
        case = next(item for item in cases if item["case_id"] == case_id)
        record = {
            "record_id": hashed,
            "family": case["family"],
            "locale": case["locale"],
            "source": case["input"].get("source"),
            "annotation": case["input"].get("candidate"),
            "benchmark_input": case["input"],
        }
        if correction_role:
            original = case["input"]["candidate"]
            proposed = case.get("verification_candidate")
            record.update({
                "after": {
                    "subject": f"https://example.test/{hashed}",
                    "predicate": str(SKOS.definition),
                    "object_kind": "literal",
                    "language": case["locale"],
                    "datatype": None,
                    "lexical": proposed if proposed is not None else original,
                },
                "before": {
                    "subject": f"https://example.test/{hashed}",
                    "predicate": str(SKOS.definition),
                    "object_kind": "literal",
                    "language": case["locale"],
                    "datatype": None,
                    "lexical": original,
                },
                "confirmed_defect": {
                    "class": case["expected_defect_types"][0],
                    "finding": case["source_ref"],
                },
                "expected_replacement": case["expected_replacement"],
            })
        records.append(record)
    response_rounds: list[list[dict[str, Any]]] = []
    prompts = _prompts()
    qualification_error = None
    try:
        for repeat in range(2):
            responses: list[dict[str, Any]] = []
            if correction_role:
                responses = _call(
                    adapter, records, qualification_schema,
                    prompt=qualification_prompt, executor=executor,
                    qualification_hash=f"qualification-eval:{repeat + 1}",
                    policy_hash=policy_hash,
                    candidate_hash=qualification_corpus_hash,
                    batch_size=int(policy["operations"]["batch_size"]),
                )
            else:
                for family in ("definition", "example", "translation"):
                    family_records = [
                        record for record in records
                        if record["family"] == family
                    ]
                    responses.extend(
                        _call(
                            adapter, family_records, qualification_schema,
                            prompt=prompts[family], executor=executor,
                            qualification_hash=(
                                f"qualification-eval:{repeat + 1}"
                            ),
                            policy_hash=policy_hash,
                            candidate_hash=qualification_corpus_hash,
                            batch_size=int(
                                policy["operations"]["batch_size"]
                            ),
                        )
                    )
            response_rounds.append(responses)
    except (BudgetExceeded, ProviderError, ValueError) as exc:
        qualification_error = str(exc)
        response_rounds = [[], []]
    responses = response_rounds[0]
    by_case = {case["case_id"]: case for case in cases}
    predictions = {}
    for item in responses:
        case_id = id_map[item["record_id"]]
        prediction = item["verdict"]
        if role == "correction-proposer" and (
            item.get("proposed_replacement")
            != by_case[case_id]["expected_replacement"]
        ):
            prediction = "invalid-replacement"
        predictions[case_id] = prediction
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
    metrics["evaluation_rounds"] = response_rounds
    now = datetime.now(UTC)
    route = next(
        value for value in policy["routes"].values()
        if value["provider"] == adapter.provider and value["model"] == adapter.model
    )
    return create_qualification(
        role=role, route_id=f"{adapter.provider}:{adapter.model}",
        provider=adapter.provider, requested_model=adapter.model,
        actual_model=adapter.model, reasoning=route["reasoning"],
        corpus_hash=qualification_corpus_hash,
        prompt_hash=qualification_prompt_hash,
        schema_hash=content_hash(canonical_json(qualification_schema)),
        policy_hash=policy_hash,
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
                assessments = [
                    {
                        "role": role,
                        "response": item,
                    }
                    for role, artifact in (
                        ("production-primary", left),
                        ("production-independent", right),
                    )
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
                    "assessments": assessments,
                }
        evaluated = evaluate_surveillance(sample, legacy, results, review_policy)
        expansions = {
            name: details["expansion_ids"]
            for name, details in evaluated["strata"].items()
            if details["expansion_ids"]
        }
        if not expansions:
            evaluated["sample"] = sample
            evaluated["results"] = results
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


def _run_changed_record_corrections(
    *,
    records: list[dict[str, Any]],
    primary: dict[str, Any],
    independent: dict[str, Any],
    candidate: Path,
    corrected_output: Path,
    ledger_output: Path,
    evidence_output: Path,
    adapters: dict[str, Any],
    qualifications: dict[str, dict[str, Any]],
    executor: ReviewExecutor,
    schema: dict[str, Any],
    model_policy: dict[str, Any],
    policy_hash: str,
    batch_size: int,
) -> dict[str, Any]:
    """Generate one protected, fully verified correction batch."""
    outputs = (corrected_output, ledger_output, evidence_output)
    if len({path.resolve() for path in outputs}) != len(outputs):
        raise ValueError("correction output paths must be distinct")
    output_parents = {path.parent.resolve() for path in outputs}
    if len(output_parents) != 1:
        raise ValueError(
            "correction outputs must share one directory for atomic publication"
        )
    output_directory = corrected_output.parent
    if output_directory.exists():
        raise FileExistsError(
            f"correction output directory already exists: {output_directory}"
        )
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    pending_directory = TemporaryDirectory(
        prefix=".ontology-correction-", dir=output_directory.parent
    )
    pending_output = Path(pending_directory.name) / corrected_output.name
    source_hash = content_hash(candidate.read_bytes())
    proposal_schema = correction_response_schema(schema, role="proposer")
    verification_schema = correction_response_schema(schema, role="verifier")
    prompts = _all_prompts()
    minimum = float(model_policy["minimum_confidence"])
    response_by_record: dict[str, list[dict[str, Any]]] = {}
    for artifact in (primary, independent):
        for response in artifact["payload"]["responses"]:
            response_by_record.setdefault(response["record_id"], []).append(
                response
            )
    correction_records = []
    for record in records:
        responses = response_by_record.get(record["record_id"], [])
        if len(responses) != 2 or any(
            response["verdict"] != "defect"
            or float(response["confidence"]) < minimum
            for response in responses
        ):
            raise ValueError(
                "changed correction root lacks two defect votes"
            )
        correction_records.append({
            **record,
            "confirmed_defect": {
                "classes": sorted({
                    defect for response in responses
                    for defect in response["defect_types"]
                }),
                "findings": [response["rationale"] for response in responses],
            },
        })

    proposer_role = "correction-proposer"
    verifier_roles = (
        "correction-verifier-1", "correction-verifier-2",
    )
    def make_caller(role, response_schema, prompt_name):
        def call(item, attempt):
            return _call(
                adapters[role],
                [{**item, "correction_attempt": attempt}],
                response_schema,
                prompt=prompts[prompt_name],
                executor=executor,
                qualification_hash=qualifications[role][
                    "qualification_hash"
                ],
                policy_hash=policy_hash,
                candidate_hash=source_hash,
                batch_size=1,
            )[0]
        return call

    proposer = make_caller(
        proposer_role, proposal_schema, "correction-proposal"
    )
    verifiers = [
        make_caller(role, verification_schema, "correction-verification")
        for role in verifier_roles
    ]
    corrections = []
    convergences = []
    for record in correction_records:
        result = converge_correction(
            record,
            proposer=proposer,
            verifier_1=verifiers[0],
            verifier_2=verifiers[1],
            proposer_route=qualifications[proposer_role]["route_id"],
            verifier_routes=[
                qualifications[role]["route_id"] for role in verifier_roles
            ],
            verifier_qualification_hashes=[
                qualifications[role]["qualification_hash"]
                for role in verifier_roles
            ],
            minimum_confidence=minimum,
            maximum_attempts=2,
        )
        convergences.append({"record_id": record["record_id"], **result})
        if result["state"] != "verified":
            raise ValueError(
                f"changed correction quarantined: {record['record_id']}"
            )
        corrections.append(result["correction"])

    transaction = apply_correction_batch(
        candidate, pending_output, corrections
    )
    validation_kwargs = {
        "policy_path": ROOT / "qa/ontology/review-policy.yaml",
        "shapes_path": ROOT / "qa/ontology/shapes.ttl",
    }
    validation = compare_validation_results(
        validate_ontology(candidate, **validation_kwargs),
        validate_ontology(pending_output, **validation_kwargs),
    )
    if validation["failures"]:
        raise ValueError(
            "changed corrections introduced deterministic failures"
        )
    corrected_hash = content_hash(pending_output.read_bytes())
    corrected_graph = Graph().parse(pending_output, format="xml")
    by_root = {item["root_record_id"]: item for item in corrections}
    corrected_records = []
    for record in correction_records:
        correction = by_root[record["record_id"]]
        updated = {
            **record,
            "annotation": correction["replacement"],
            "after": {
                **record["after"],
                "lexical": correction["replacement"],
            },
        }
        updated["context"] = build_graph_context(
            corrected_graph, updated, risk_evidence=[]
        )
        corrected_records.append(updated)
    rereviews = {}
    for role in ("production-primary", "production-independent"):
        responses = []
        for family in ("definition", "example", "translation"):
            family_records = [
                record for record in corrected_records
                if record["family"] == family
            ]
            responses.extend(_call(
                adapters[role], family_records, schema,
                prompt=prompts[family], executor=executor,
                qualification_hash=qualifications[role][
                    "qualification_hash"
                ],
                policy_hash=policy_hash,
                candidate_hash=corrected_hash,
                batch_size=batch_size,
            ))
        if (
            {item["record_id"] for item in responses}
            != {item["record_id"] for item in corrected_records}
            or len(responses) != len(corrected_records)
            or any(
                item["verdict"] != "pass"
                or float(item["confidence"]) < minimum
                for item in responses
            )
        ):
            raise ValueError(
                f"changed corrected candidate failed final rereview: {role}"
            )
        rereviews[role] = responses
    evidence_body = {
        "schema_version": 1,
        "source_hash": source_hash,
        "candidate_hash": corrected_hash,
        "policy_hash": policy_hash,
        "prompt_hash": content_hash(canonical_json(prompts)),
        "qualifications": qualifications,
        "source_reviews": {
            "production-primary": primary["payload"]["responses"],
            "production-independent": independent["payload"]["responses"],
        },
        "convergences": convergences,
        "transaction": transaction,
        "validation": validation,
        "rereviews": rereviews,
        "budget": executor.budget.snapshot(),
        "cache_hits": executor.cache_hits,
    }
    evidence = {
        "evidence_hash": content_hash(canonical_json(evidence_body)),
        **evidence_body,
    }
    pending_ledger = Path(pending_directory.name) / ledger_output.name
    pending_evidence = Path(pending_directory.name) / evidence_output.name
    pending_ledger.write_bytes(canonical_json(corrections) + b"\n")
    pending_evidence.write_bytes(canonical_json(evidence) + b"\n")
    Path(pending_directory.name).replace(output_directory)
    pending_directory.cleanup()
    return {
        "status": "correction_ready",
        "correction_count": len(corrections),
        "source_hash": source_hash,
        "candidate_hash": corrected_hash,
        "ledger_hash": content_hash(canonical_json(corrections)),
        "evidence_hash": evidence["evidence_hash"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--reviewed-sha", required=True)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--cache", type=Path, default=Path(".ontology-qa-cache"))
    parser.add_argument("--correction-ledger", type=Path)
    parser.add_argument("--correction-evidence", type=Path)
    parser.add_argument("--correction-source", type=Path)
    parser.add_argument("--corrected-output", type=Path)
    parser.add_argument("--generated-correction-ledger", type=Path)
    parser.add_argument("--generated-correction-evidence", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.reviewed_sha):
        print("trusted ontology QA failed: reviewed SHA is not immutable", file=sys.stderr)
        return 1
    generated_outputs = (
        args.corrected_output,
        args.generated_correction_ledger,
        args.generated_correction_evidence,
    )
    if any(generated_outputs) and not all(generated_outputs):
        print(
            "trusted ontology QA failed: generated correction outputs must be supplied together",
            file=sys.stderr,
        )
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
            or args.correction_source is not None
        )
        if closed_debt and not (
            args.correction_ledger and args.correction_evidence
        ):
            raise ValueError(
                "candidate closes confirmed debt without correction evidence"
            )
        if supplied_correction_artifacts:
            if not (
                args.correction_ledger
                and args.correction_evidence
                and args.correction_source
            ):
                raise ValueError(
                    "correction source, ledger, and evidence must be supplied together"
                )
            correction_lineage = verify_correction_lineage(
                source_path=args.correction_source,
                candidate_path=args.candidate,
                ledger_path=args.correction_ledger,
                evidence_path=args.correction_evidence,
                schema_path=ROOT / "schemas/ontology-correction.schema.json",
                minimum_confidence=float(
                    model_policy["minimum_confidence"]
                ),
                expected_policy_hash=policy_hash,
                expected_prompt_hash=_prompt_bundle_hash(),
                expected_routes={
                    role: (
                        f"{model_policy['routes'][route_name]['provider']}:"
                        f"{model_policy['routes'][route_name]['model']}"
                    )
                    for role, route_name in {
                        "production-primary": "primary",
                        "production-independent": "independent",
                        "correction-proposer": "correction_proposer",
                        "correction-verifier-1": "correction_verifier_1",
                        "correction-verifier-2": "correction_verifier_2",
                    }.items()
                },
            )
            ledger_roots = {
                item["root_record_id"]
                for item in json.loads(
                    args.correction_ledger.read_text(encoding="utf-8")
                )
            }
            if closed_debt and ledger_roots != closed_roots:
                raise ValueError(
                    "correction ledger roots differ from closed confirmed debt"
                )
            bundle.snapshot("correction-source.owl", args.correction_source)
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
        defect_ids = {
            record_id
            for record_id, state in reconciliation.get("records", {}).items()
            if state == "defect_confirmed"
        }
        if defect_ids:
            if not all(generated_outputs):
                raise ValueError(
                    "confirmed changed-record defects require protected correction outputs"
                )
            result = _run_changed_record_corrections(
                records=[
                    record for record in records
                    if record["record_id"] in defect_ids
                ],
                primary=primary,
                independent=independent,
                candidate=args.candidate,
                corrected_output=args.corrected_output,
                ledger_output=args.generated_correction_ledger,
                evidence_output=args.generated_correction_evidence,
                adapters=adapters,
                qualifications=qualifications,
                executor=executor,
                schema=schema,
                model_policy=model_policy,
                policy_hash=policy_hash,
                batch_size=int(operations["batch_size"]),
            )
            print(json.dumps(result, sort_keys=True))
            return 2
        legacy = build_legacy_records(
            candidate_graph,
            {
                surveillance_record_id(item["after"])
                for item in manifest["payload"]["records"]
                if item.get("after")
            },
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
