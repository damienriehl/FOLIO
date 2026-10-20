"""Changed-record correction convergence and atomic batch publication."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from rdflib import Graph

from .correction_artifacts import (
    _canonical_json_bytes, _require_exact_response_set,
)
from .execution import ReviewExecutor
from .records import canonical_json, content_hash


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
    ROOT: Path,
    _all_prompts: Callable,
    _call: Callable,
    correction_response_schema: Callable,
    build_graph_context: Callable,
    converge_correction: Callable,
    apply_correction_batch: Callable,
    validate_ontology: Callable,
    compare_validation_results: Callable,
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
        try:
            _require_exact_response_set(
                corrected_records, responses,
                expected_count=len(corrected_records),
            )
        except ValueError:
            raise ValueError(
                f"changed corrected candidate failed final rereview: {role}"
            ) from None
        if (
            any(
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
    pending_ledger.write_bytes(_canonical_json_bytes(corrections))
    pending_evidence.write_bytes(_canonical_json_bytes(evidence))
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
