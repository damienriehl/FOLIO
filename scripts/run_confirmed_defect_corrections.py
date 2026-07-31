#!/usr/bin/env python3
"""Generate, verify, apply, and rereview confirmed ontology corrections."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

import yaml
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, SKOS

from ontology_qa.context import build_graph_context
from ontology_qa.correction_pipeline import converge_correction
from ontology_qa.corrections import apply_correction_batch
from ontology_qa.debt import debt_root_id, load_debt, validate_debt_targets
from ontology_qa.evals import load_model_policy
from ontology_qa.execution import ImmutableReviewCache, ReviewBudget, ReviewExecutor
from ontology_qa.qualification import validate_role_separation
from ontology_qa.records import AnnotationValue, canonical_json, content_hash
from ontology_qa.validators import compare_validation_results, validate_ontology
from run_trusted_ontology_qa import (
    ROOT, _adapter, _call, _prompt_bundle_hash, _prompts, _qualify,
)


def _source_label(graph: Graph, subject: URIRef) -> str:
    for predicate in (RDFS.label, SKOS.prefLabel):
        values = [
            str(value) for value in graph.objects(subject, predicate)
            if isinstance(value, Literal)
            and (value.language or "en").lower().startswith("en")
        ]
        if values:
            return sorted(values)[0]
    return str(subject)


def build_debt_records(
    ontology_path: str | Path,
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    graph = Graph().parse(ontology_path, format="xml")
    records = []
    for entry in entries:
        values = [
            value
            for value in graph.objects(
                URIRef(entry["subject"]), URIRef(entry["predicate"])
            )
            if isinstance(value, Literal)
            and (value.language.lower() if value.language else None)
            == entry["language"]
            and (str(value.datatype) if value.datatype else None)
            == entry["datatype"]
        ]
        matches = [
            value for value in values
            if AnnotationValue(
                entry["subject"], entry["predicate"], str(value),
                language=value.language,
                datatype=str(value.datatype) if value.datatype else None,
            ).value_hash == entry["current_hash"]
        ]
        if len(matches) != 1:
            raise ValueError(f"debt target is stale: {entry['debt_id']}")
        value = matches[0]
        locale = (value.language or "en").lower()
        family = (
            "definition"
            if entry["predicate"] == str(SKOS.definition)
            else "translation"
        )
        after = {
            "subject": entry["subject"],
            "predicate": entry["predicate"],
            "object_kind": "literal",
            "language": value.language,
            "datatype": str(value.datatype) if value.datatype else None,
            "lexical": str(value),
        }
        record = {
            "record_id": debt_root_id(entry),
            "debt_id": entry["debt_id"],
            "family": family,
            "locale": locale,
            "source": _source_label(graph, URIRef(entry["subject"])),
            "annotation": str(value),
            "after": after,
            "confirmed_defect": {
                "class": entry["defect_class"],
                "finding": entry["finding"],
                "source": entry["discovery"],
            },
        }
        record["context"] = build_graph_context(graph, record, risk_evidence=[])
        records.append(record)
    return sorted(records, key=lambda item: item["record_id"])


def _require_exact_verdicts(
    records: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    *,
    verdict: str,
    minimum_confidence: float,
) -> None:
    expected = {record["record_id"] for record in records}
    actual = {response["record_id"] for response in responses}
    if actual != expected or len(actual) != len(responses):
        raise ValueError("assessment response set is incomplete")
    failures = sorted(
        response["record_id"] for response in responses
        if response["verdict"] != verdict
        or float(response["confidence"]) < minimum_confidence
    )
    if failures:
        raise ValueError(
            f"required {verdict} verdict did not converge: {failures}"
        )


def _require_exact_response_set(
    records: list[dict[str, Any]],
    responses: list[dict[str, Any]],
) -> None:
    expected = {record["record_id"] for record in records}
    actual = {response["record_id"] for response in responses}
    if actual != expected or len(actual) != len(responses):
        raise ValueError("assessment response set is incomplete")


def _write_once(path: Path, value: Any) -> None:
    data = canonical_json(value) + b"\n"
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"append-only output exists: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _correction_response_schema(
    schema: dict[str, Any], *, role: str
) -> dict[str, Any]:
    projected = json.loads(json.dumps(schema))
    projected.pop("allOf", None)
    if role == "proposer":
        projected["properties"]["verdict"] = {"enum": ["defect"]}
        projected["properties"]["proposed_replacement"] = {
            "type": "string", "minLength": 1,
        }
    elif role == "verifier":
        projected["properties"]["proposed_replacement"] = {"type": "null"}
    else:
        raise ValueError(f"unknown correction schema role: {role}")
    return projected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument(
        "--evidence", required=True, type=Path,
        help="Append-only correction evidence JSON.",
    )
    parser.add_argument(
        "--cache", type=Path, default=Path(".ontology-qa-cache")
    )
    parser.add_argument(
        "--route-policy-overlay", type=Path,
        help="Separately hashed complete route replacement after qualification.",
    )
    args = parser.parse_args()
    candidate_path = args.output.with_suffix(args.output.suffix + ".pending")
    try:
        entries = load_debt(ROOT / "qa/ontology/confirmed-defects.json")
        validate_debt_targets(args.source, entries)
        records = build_debt_records(args.source, entries)
        model_policy_path = ROOT / "qa/ontology/model-policy.yaml"
        model_policy = load_model_policy(model_policy_path)
        review_policy_path = ROOT / "qa/ontology/review-policy.yaml"
        overlay_bytes = b""
        if args.route_policy_overlay:
            overlay = yaml.safe_load(
                args.route_policy_overlay.read_text(encoding="utf-8")
            )
            if overlay.get("version") != 1:
                raise ValueError("unsupported route-policy overlay")
            if set(overlay.get("routes", {})) != set(model_policy["routes"]):
                raise ValueError("route-policy overlay must replace every route")
            model_policy = copy.deepcopy(model_policy)
            model_policy["routes"] = overlay["routes"]
            model_policy["operations"]["pricing"].update(overlay["pricing"])
            model_policy["operations"].update(overlay.get("operations", {}))
            overlay_bytes = args.route_policy_overlay.read_bytes()
        schema = json.loads(
            (ROOT / model_policy["review_schema"]).read_text(encoding="utf-8")
        )
        policy_hash = content_hash(
            model_policy_path.read_bytes()
            + review_policy_path.read_bytes()
            + overlay_bytes
        )
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
        maximum_output = int(operations["maximum_output_tokens_per_request"])
        role_routes = {
            "production-primary": "primary",
            "production-independent": "independent",
            "correction-proposer": "correction_proposer",
            "correction-verifier-1": "correction_verifier_1",
            "correction-verifier-2": "correction_verifier_2",
            "benchmark-adjudicator": "benchmark_adjudicator",
        }
        adapters = {
            role: _adapter(
                model_policy["routes"][route],
                maximum_output_tokens=maximum_output,
            )
            for role, route in role_routes.items()
        }
        qualifications = {
            role: _qualify(
                adapter, role, model_policy, schema, policy_hash,
                executor=executor,
            )
            for role, adapter in adapters.items()
        }
        for role, qualification in list(qualifications.items()):
            if qualification["status"] != "qualified":
                qualifications[role] = _qualify(
                    adapters[role], role, model_policy, schema,
                    policy_hash, executor=executor,
                )
        validate_role_separation(list(qualifications.values()))
        rejected = sorted(
            role for role, item in qualifications.items()
            if item["status"] != "qualified"
        )
        if rejected:
            raise ValueError(f"correction routes failed qualification: {rejected}")

        source_hash = content_hash(args.source.read_bytes())
        batch_size = int(operations["batch_size"])
        prompts = _prompts()

        source_review_routes = {
            "production-primary": (
                adapters["production-primary"],
                qualifications["production-primary"],
                policy_hash,
            ),
            "production-independent": (
                adapters["production-independent"],
                qualifications["production-independent"],
                policy_hash,
            ),
        }
        source_reviews: dict[str, list[dict[str, Any]]] = {}
        for role, (adapter, qualification, review_policy_hash) in (
            source_review_routes.items()
        ):
            responses = []
            for family in ("definition", "translation"):
                family_records = [
                    record for record in records
                    if record["family"] == family
                ]
                responses.extend(_call(
                    adapter, family_records, schema, prompt=prompts[family],
                    executor=executor,
                    qualification_hash=qualification["qualification_hash"],
                    policy_hash=review_policy_hash,
                    candidate_hash=source_hash, batch_size=batch_size,
                ))
            _require_exact_verdicts(
                records, responses, verdict="defect",
                minimum_confidence=float(model_policy["minimum_confidence"]),
            )
            source_reviews[role] = responses

        proposal_prompt = (
            ROOT / "qa/ontology/prompts/correction-proposal.md"
        ).read_text(encoding="utf-8")
        verification_prompt = (
            ROOT / "qa/ontology/prompts/correction-verification.md"
        ).read_text(encoding="utf-8")
        proposal_schema = _correction_response_schema(
            schema, role="proposer"
        )
        verification_schema = _correction_response_schema(
            schema, role="verifier"
        )
        convergences = []
        corrections = []
        for record in records:
            def propose(item, attempt):
                request = [{**item, "correction_attempt": attempt}]
                return _call(
                    adapters["correction-proposer"], request,
                    proposal_schema, prompt=proposal_prompt,
                    executor=executor,
                    qualification_hash=qualifications[
                        "correction-proposer"
                    ]["qualification_hash"],
                    policy_hash=policy_hash, candidate_hash=source_hash,
                    batch_size=1,
                )[0]

            def verify(role):
                def callback(item, attempt):
                    request = [{**item, "correction_attempt": attempt}]
                    return _call(
                        adapters[role], request, verification_schema,
                        prompt=verification_prompt, executor=executor,
                        qualification_hash=qualifications[role][
                            "qualification_hash"
                        ],
                        policy_hash=policy_hash, candidate_hash=source_hash,
                        batch_size=1,
                    )[0]
                return callback

            result = converge_correction(
                record, proposer=propose,
                verifier_1=verify("correction-verifier-1"),
                verifier_2=verify("correction-verifier-2"),
                proposer_route=qualifications[
                    "correction-proposer"
                ]["route_id"],
                verifier_routes=[
                    qualifications["correction-verifier-1"]["route_id"],
                    qualifications["correction-verifier-2"]["route_id"],
                ],
                verifier_qualification_hashes=[
                    qualifications[
                        "correction-verifier-1"
                    ]["qualification_hash"],
                    qualifications[
                        "correction-verifier-2"
                    ]["qualification_hash"],
                ],
                minimum_confidence=float(model_policy["minimum_confidence"]),
                maximum_attempts=2,
            )
            convergences.append({
                "record_id": record["record_id"], **result,
            })
            if result["state"] != "verified":
                raise ValueError(
                    f"correction quarantined: {record['debt_id']}"
                )
            corrections.append(result["correction"])

        validation_kwargs = {
            "policy_path": review_policy_path,
            "shapes_path": ROOT / "qa/ontology/shapes.ttl",
        }
        rereview_routes = {
            "production-primary": (
                adapters["production-primary"],
                qualifications["production-primary"],
                policy_hash,
            ),
            "production-independent": (
                adapters["production-independent"],
                qualifications["production-independent"],
                policy_hash,
            ),
        }
        minimum_confidence = float(model_policy["minimum_confidence"])

        def apply_validate_rereview():
            transaction = apply_correction_batch(
                args.source, candidate_path, corrections
            )
            validation = compare_validation_results(
                validate_ontology(args.source, **validation_kwargs),
                validate_ontology(candidate_path, **validation_kwargs),
            )
            if validation["failures"]:
                raise ValueError(
                    "corrected candidate introduced deterministic failures"
                )
            corrected_graph = Graph().parse(candidate_path, format="xml")
            by_root = {
                item["root_record_id"]: item for item in corrections
            }
            corrected_records = []
            for record in records:
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
            corrected_hash = content_hash(candidate_path.read_bytes())
            rereviews = {}
            failed = set()
            for role, (adapter, qualification, review_policy_hash) in (
                rereview_routes.items()
            ):
                responses = []
                for family in ("definition", "translation"):
                    items = [
                        record for record in corrected_records
                        if record["family"] == family
                    ]
                    responses.extend(_call(
                        adapter, items, schema, prompt=prompts[family],
                        executor=executor,
                        qualification_hash=qualification[
                            "qualification_hash"
                        ],
                        policy_hash=review_policy_hash,
                        candidate_hash=corrected_hash,
                        batch_size=batch_size,
                    ))
                _require_exact_response_set(corrected_records, responses)
                rereviews[role] = responses
                failed.update(
                    item["record_id"] for item in responses
                    if item["verdict"] != "pass"
                    or float(item["confidence"]) < minimum_confidence
                )
            return (
                transaction, validation, corrected_hash, rereviews, failed
            )

        transaction, validation, corrected_hash, rereviews, failed = (
            apply_validate_rereview()
        )
        if failed:
            by_record = {
                record["record_id"]: record for record in records
            }
            by_correction = {
                item["root_record_id"]: item for item in corrections
            }
            for record_id in sorted(failed):
                record = by_record[record_id]
                prior = by_correction[record_id]
                feedback = [
                    {
                        "route": role,
                        "verdict": response["verdict"],
                        "confidence": response["confidence"],
                        "rationale": response["rationale"],
                    }
                    for role, responses in rereviews.items()
                    for response in responses
                    if response["record_id"] == record_id
                    and (
                        response["verdict"] != "pass"
                        or float(response["confidence"]) < minimum_confidence
                    )
                ]
                retry_record = {
                    **record,
                    "rejected_replacement": prior["replacement"],
                    "final_rereview_feedback": feedback,
                }

                def retry_propose(item, _attempt):
                    return _call(
                        adapters["correction-proposer"],
                        [{**item, "correction_attempt": 2}],
                        proposal_schema, prompt=proposal_prompt,
                        executor=executor,
                        qualification_hash=qualifications[
                            "correction-proposer"
                        ]["qualification_hash"],
                        policy_hash=policy_hash,
                        candidate_hash=source_hash, batch_size=1,
                    )[0]

                def retry_verify(role):
                    def callback(item, _attempt):
                        return _call(
                            adapters[role],
                            [{**item, "correction_attempt": 2}],
                            verification_schema,
                            prompt=verification_prompt,
                            executor=executor,
                            qualification_hash=qualifications[role][
                                "qualification_hash"
                            ],
                            policy_hash=policy_hash,
                            candidate_hash=source_hash, batch_size=1,
                        )[0]
                    return callback

                result = converge_correction(
                    retry_record, proposer=retry_propose,
                    verifier_1=retry_verify("correction-verifier-1"),
                    verifier_2=retry_verify("correction-verifier-2"),
                    proposer_route=qualifications[
                        "correction-proposer"
                    ]["route_id"],
                    verifier_routes=[
                        qualifications["correction-verifier-1"]["route_id"],
                        qualifications["correction-verifier-2"]["route_id"],
                    ],
                    verifier_qualification_hashes=[
                        qualifications["correction-verifier-1"][
                            "qualification_hash"
                        ],
                        qualifications["correction-verifier-2"][
                            "qualification_hash"
                        ],
                    ],
                    minimum_confidence=float(
                        model_policy["minimum_confidence"]
                    ),
                    maximum_attempts=1,
                )
                if (
                    result["state"] != "verified"
                    or result["correction"]["replacement_hash"]
                    == prior["replacement_hash"]
                ):
                    raise ValueError(
                        f"final rereview correction quarantined: {record_id}"
                    )
                by_correction[record_id] = result["correction"]
                convergences.append({
                    "record_id": record_id,
                    "trigger": "final-rereview", **result,
                })
            corrections = [
                by_correction[record["record_id"]] for record in records
            ]
            (
                transaction, validation, corrected_hash, rereviews, failed
            ) = apply_validate_rereview()
            if failed:
                raise ValueError(
                    f"final rereview correction exhausted: {sorted(failed)}"
                )

        evidence = {
            "schema_version": 1,
            "source_hash": source_hash,
            "candidate_hash": corrected_hash,
            "policy_hash": policy_hash,
            "prompt_hash": _prompt_bundle_hash(),
            "qualifications": qualifications,
            "source_reviews": source_reviews,
            "convergences": convergences,
            "transaction": transaction,
            "validation": validation,
            "rereviews": rereviews,
            "budget": budget.snapshot(),
            "cache_hits": executor.cache_hits,
        }
        evidence = {
            "evidence_hash": content_hash(canonical_json(evidence)),
            **evidence,
        }
        _write_once(args.ledger, corrections)
        _write_once(args.evidence, evidence)
        if args.output.exists():
            raise FileExistsError(f"output already exists: {args.output}")
        candidate_path.replace(args.output)
        print(json.dumps({
            "correction_count": len(corrections),
            "output_hash": corrected_hash,
            "evidence_hash": evidence["evidence_hash"],
            "cache_hits": executor.cache_hits,
        }, sort_keys=True))
        return 0
    except Exception as exc:
        if os.environ.get("ONTOLOGY_QA_DEBUG") == "1":
            traceback.print_exc()
        print(f"confirmed correction run failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
