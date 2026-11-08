"""Offline verification for confirmed-defect correction lineages."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from jsonschema import Draft202012Validator

from .corrections import apply_correction_batch
from .correction_pipeline import correction_response_schema
from .evals import (
    correction_cases, load_slice_controls, score_qualification_rounds,
)
from .records import canonical_json, content_hash
from .reporting import validate_qualification_hash
from .qualification import create_qualification


def _canonical_json_file(path: Path) -> Any:
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != canonical_json(value) + b"\n":
        raise ValueError(f"correction artifact is not canonical: {path.name}")
    return value


def verify_correction_lineage(
    *,
    source_path: str | Path,
    candidate_path: str | Path,
    ledger_path: str | Path,
    evidence_path: str | Path,
    schema_path: str | Path,
    minimum_confidence: float,
    expected_policy_hash: str | None = None,
    expected_prompt_hash: str | None = None,
    expected_routes: dict[str, str] | None = None,
    model_policy: dict[str, Any] | None = None,
    slice_controls_path: str | Path | None = None,
    review_schema_path: str | Path | None = None,
    proposal_prompt_path: str | Path | None = None,
    verification_prompt_path: str | Path | None = None,
) -> dict[str, Any]:
    """Reapply and verify a complete correction lineage without providers."""
    source_path = Path(source_path)
    candidate_path = Path(candidate_path)
    ledger = _canonical_json_file(Path(ledger_path))
    evidence = _canonical_json_file(Path(evidence_path))
    if not isinstance(ledger, list) or not ledger:
        raise ValueError("correction ledger must be a non-empty list")
    validator = Draft202012Validator(
        json.loads(Path(schema_path).read_text(encoding="utf-8"))
    )
    for correction in ledger:
        validator.validate(correction)
    root_ids = [item["root_record_id"] for item in ledger]
    revision_ids = [item["revision_id"] for item in ledger]
    if len(root_ids) != len(set(root_ids)):
        raise ValueError("correction ledger contains duplicate roots")
    if len(revision_ids) != len(set(revision_ids)):
        raise ValueError("correction ledger contains duplicate revisions")

    evidence_body = dict(evidence)
    claimed_evidence_hash = evidence_body.pop("evidence_hash", None)
    if content_hash(canonical_json(evidence_body)) != claimed_evidence_hash:
        raise ValueError("correction evidence hash mismatch")
    source_hash = content_hash(source_path.read_bytes())
    candidate_hash = content_hash(candidate_path.read_bytes())
    if (
        evidence.get("source_hash") != source_hash
        or evidence.get("candidate_hash") != candidate_hash
    ):
        raise ValueError("correction evidence ontology binding mismatch")
    transaction = evidence.get("transaction", {})
    if (
        transaction.get("source_hash") != source_hash
        or transaction.get("output_hash") != candidate_hash
        or transaction.get("correction_count") != len(ledger)
        or set(transaction.get("revision_ids", [])) != set(revision_ids)
    ):
        raise ValueError("correction transaction does not match ledger")

    convergences = evidence.get("convergences", [])
    verified = {
        item["record_id"]: item["correction"]
        for item in convergences
        if item.get("state") == "verified" and "correction" in item
    }
    if set(verified) != set(root_ids):
        raise ValueError("correction convergence roots are incomplete")
    if any(verified[item["root_record_id"]] != item for item in ledger):
        raise ValueError("correction ledger differs from verified convergence")

    qualifications = evidence.get("qualifications", {})
    for qualification in qualifications.values():
        validate_qualification_hash(qualification)
    required_roles = {
        "production-primary", "production-independent",
        "correction-proposer", "correction-verifier-1",
        "correction-verifier-2",
    }
    if not required_roles.issubset(qualifications):
        raise ValueError("correction qualifications are incomplete")
    if (
        expected_policy_hash is not None
        and evidence.get("policy_hash") != expected_policy_hash
    ):
        raise ValueError("correction evidence policy binding mismatch")
    if (
        expected_prompt_hash is not None
        and evidence.get("prompt_hash") != expected_prompt_hash
    ):
        raise ValueError("correction evidence prompt binding mismatch")
    if expected_routes is not None:
        for role in required_roles:
            qualification = qualifications[role]
            if (
                qualification.get("role") != role
                or qualification.get("route_id")
                != expected_routes.get(role)
                or qualification.get("policy_hash") != expected_policy_hash
                or qualification.get("status") != "qualified"
            ):
                raise ValueError(
                    f"correction qualification binding mismatch: {role}"
                )
    semantic_inputs = (
        model_policy, slice_controls_path, review_schema_path,
        proposal_prompt_path, verification_prompt_path,
    )
    if any(item is not None for item in semantic_inputs):
        if not all(item is not None for item in semantic_inputs):
            raise ValueError("correction qualification snapshots are incomplete")
        required_slices = {
            (family, locale)
            for family, locales in model_policy["required_slices"].items()
            for locale in locales
        }
        controls = load_slice_controls(slice_controls_path, required_slices)
        base_schema = json.loads(Path(review_schema_path).read_text(encoding="utf-8"))
        for role in (
            "correction-proposer", "correction-verifier-1",
            "correction-verifier-2",
        ):
            qualification = qualifications[role]
            role_cases = correction_cases(controls, role=role)
            role_schema = correction_response_schema(
                base_schema,
                role="proposer" if role == "correction-proposer" else "verifier",
            )
            prompt_path = (
                proposal_prompt_path if role == "correction-proposer"
                else verification_prompt_path
            )
            if (
                qualification.get("corpus_hash")
                != content_hash(canonical_json(role_cases))
                or qualification.get("schema_hash")
                != content_hash(canonical_json(role_schema))
                or qualification.get("prompt_hash")
                != content_hash(Path(prompt_path).read_text(encoding="utf-8"))
            ):
                raise ValueError(f"correction qualification input mismatch: {role}")
            rounds = qualification.get("metrics", {}).get("evaluation_rounds")
            if not isinstance(rounds, list) or len(rounds) != 2:
                raise ValueError(f"correction qualification lacks rounds: {role}")
            recomputed = score_qualification_rounds(
                role_cases, rounds, role=role,
                minimum_cases_per_slice=int(
                    model_policy["minimum_scored_cases_per_slice"]
                ), required_slices=required_slices,
            )
            for field in (
                "scored_count", "missing_case_ids", "accuracy",
                "defect_recall", "false_accept_rate", "unsupported_slices",
                "slice_metrics", "repeat_stability", "round_metrics",
            ):
                if qualification["metrics"].get(field) != recomputed.get(field):
                    raise ValueError(
                        f"correction qualification metric differs: {role}:{field}"
                    )
            replayed = create_qualification(
                role=role, route_id=qualification["route_id"],
                provider=qualification["provider"],
                requested_model=qualification["requested_model"],
                actual_model=qualification["actual_model"],
                reasoning=qualification["reasoning"],
                corpus_hash=qualification["corpus_hash"],
                prompt_hash=qualification["prompt_hash"],
                schema_hash=qualification["schema_hash"],
                policy_hash=qualification["policy_hash"], metrics=recomputed,
                thresholds=qualification["thresholds"],
                qualified_at=qualification["qualified_at"],
                valid_until=qualification["valid_until"],
            )
            if replayed["status"] != qualification["status"]:
                raise ValueError(f"correction qualification status differs: {role}")
    if (
        qualifications["production-primary"]["provider"]
        == qualifications["production-independent"]["provider"]
    ):
        raise ValueError("correction final review is not cross-provider")
    if (
        qualifications["correction-verifier-1"]["provider"]
        == qualifications["correction-verifier-2"]["provider"]
    ):
        raise ValueError("correction verification is not cross-provider")
    proposer = qualifications["correction-proposer"]
    verifier_1 = qualifications["correction-verifier-1"]
    verifier_2 = qualifications["correction-verifier-2"]
    for correction in ledger:
        if (
            correction["proposer_route"] != proposer["route_id"]
            or correction["verifier_routes"]
            != [verifier_1["route_id"], verifier_2["route_id"]]
            or correction["verifier_qualification_hashes"]
            != [
                verifier_1["qualification_hash"],
                verifier_2["qualification_hash"],
            ]
        ):
            raise ValueError(
                "correction vote bindings differ from qualifications"
            )

    rereviews = evidence.get("rereviews", {})
    if set(rereviews) != {
        "production-primary", "production-independent"
    }:
        raise ValueError("correction final rereview routes are incomplete")
    for responses in rereviews.values():
        if (
            {item.get("record_id") for item in responses} != set(root_ids)
            or len(responses) != len(root_ids)
            or any(
                item.get("verdict") != "pass"
                or float(item.get("confidence", 0)) < minimum_confidence
                for item in responses
            )
        ):
            raise ValueError("correction final rereview did not converge")

    with TemporaryDirectory(prefix="folio-correction-replay-") as directory:
        replayed = Path(directory) / "candidate.owl"
        replay = apply_correction_batch(source_path, replayed, ledger)
        if replay["output_hash"] != candidate_hash:
            raise ValueError("replayed correction bytes differ from candidate")
    return {
        "correction_count": len(ledger),
        "ledger_hash": content_hash(canonical_json(ledger)),
        "evidence_hash": claimed_evidence_hash,
        "source_hash": source_hash,
        "candidate_hash": candidate_hash,
    }
