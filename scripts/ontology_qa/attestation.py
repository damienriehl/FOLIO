"""Acceptance-attestation predicates and trusted handoff verification."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .records import canonical_json, content_hash
from .replay import replay_bundle


def build_acceptance_predicate(
    *,
    repository: str,
    workflow_ref: str,
    commit_sha: str,
    tree_sha: str,
    run_id: str,
    run_attempt: str,
    report: dict[str, Any],
    evidence_bundle_digest: str,
    expires_at: str,
    candidate_repository: str | None = None,
) -> dict[str, Any]:
    if report["payload"].get("release_decision") != "merge_gate_passed":
        raise ValueError("only a passing release report can be attested")
    predicate = {
        "predicate_type": "https://folio.openlegalstandard.org/attestation/ontology-qa/v1",
        "repository": repository,
        "candidate_repository": candidate_repository or repository,
        "workflow_ref": workflow_ref,
        "commit_sha": commit_sha,
        "tree_sha": tree_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "ontology_hash": report["candidate_hash"],
        "baseline_hash": report["baseline_hash"],
        "policy_hash": report["policy_hash"],
        "report_hash": report["artifact_hash"],
        "stage_hashes": report["payload"]["stage_hashes"],
        "evidence_bundle_digest": evidence_bundle_digest,
        "expires_at": expires_at,
    }
    return {"predicate_hash": content_hash(canonical_json(predicate)), **predicate}


def verify_acceptance_handoff(
    predicate: dict[str, Any],
    *,
    expected_repository: str,
    expected_workflow_ref: str,
    expected_commit_sha: str,
    expected_tree_sha: str,
    candidate_path: str | Path,
    bundle_path: str | Path,
    report_schema_path: str | Path,
    bundle_digest: str,
    now: datetime | None = None,
    expected_candidate_repository: str | None = None,
) -> dict[str, Any]:
    body = dict(predicate)
    claimed = body.pop("predicate_hash", None)
    if content_hash(canonical_json(body)) != claimed:
        raise ValueError("acceptance predicate hash mismatch")
    expected = {
        "repository": expected_repository,
        "candidate_repository": expected_candidate_repository or expected_repository,
        "workflow_ref": expected_workflow_ref,
        "commit_sha": expected_commit_sha,
        "tree_sha": expected_tree_sha,
    }
    for field, value in expected.items():
        if predicate.get(field) != value:
            raise ValueError(f"attestation identity mismatch: {field}")
    expiry = datetime.fromisoformat(predicate["expires_at"].replace("Z", "+00:00"))
    if (now or datetime.now(UTC)) >= expiry:
        raise ValueError("acceptance attestation expired")
    if predicate["evidence_bundle_digest"] != bundle_digest:
        raise ValueError("evidence bundle digest mismatch")
    if content_hash(Path(candidate_path).read_bytes()) != predicate["ontology_hash"]:
        raise ValueError("candidate ontology does not match attestation")
    replay = replay_bundle(bundle_path, report_schema_path=report_schema_path)
    if replay["report_hash"] != predicate["report_hash"]:
        raise ValueError("replayed report does not match attestation")
    return {"verified": True, "report_hash": replay["report_hash"], "ontology_hash": predicate["ontology_hash"]}
