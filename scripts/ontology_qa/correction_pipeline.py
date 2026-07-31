"""Bounded, proposer-excluded correction convergence."""

from __future__ import annotations

from typing import Any, Callable

from .corrections import make_correction
from .records import AnnotationValue

ProposalRoute = Callable[[dict[str, Any], int], dict[str, Any]]
VerifierRoute = Callable[[dict[str, Any], int], dict[str, Any]]


def converge_correction(
    record: dict[str, Any],
    *,
    proposer: ProposalRoute,
    verifier_1: VerifierRoute,
    verifier_2: VerifierRoute,
    proposer_route: str,
    verifier_routes: list[str],
    verifier_qualification_hashes: list[str],
    minimum_confidence: float,
    maximum_attempts: int = 2,
) -> dict[str, Any]:
    """Produce one verified correction or a terminal quarantine."""
    if maximum_attempts < 1:
        raise ValueError("maximum correction attempts must be positive")
    if len(verifier_routes) != 2:
        raise ValueError("exactly two correction verifiers are required")
    value = record.get("after") or record.get("before")
    if not value:
        raise ValueError("correction root lacks an annotation value")
    seen_replacements: set[str] = set()
    attempts = []
    for attempt in range(1, maximum_attempts + 1):
        proposal = proposer(record, attempt)
        if proposal.get("record_id") != record["record_id"]:
            raise ValueError("correction proposer returned a mismatched record ID")
        replacement = proposal.get("proposed_replacement")
        if not isinstance(replacement, str) or not replacement.strip():
            attempts.append({
                "attempt": attempt, "state": "proposal_rejected",
                "reason": "missing replacement",
            })
            continue
        candidate = AnnotationValue(
            value["subject"], value["predicate"], replacement,
            language=value.get("language"), datatype=value.get("datatype"),
        )
        if candidate.value_hash in seen_replacements:
            return {
                "state": "quarantined", "reason": "correction cycle",
                "attempts": attempts,
            }
        seen_replacements.add(candidate.value_hash)
        verification_record = {
            **record,
            "before": value,
            "after": candidate.canonical(),
            "proposed_replacement_hash": candidate.value_hash,
        }
        votes = [
            verifier_1(verification_record, attempt),
            verifier_2(verification_record, attempt),
        ]
        verified = all(
            vote.get("record_id") == record["record_id"]
            and vote.get("verdict") == "pass"
            and float(vote.get("confidence", 0)) >= minimum_confidence
            and vote.get("proposed_replacement") is None
            for vote in votes
        )
        attempts.append({
            "attempt": attempt,
            "replacement_hash": candidate.value_hash,
            "verdicts": [vote.get("verdict") for vote in votes],
            "state": "verified" if verified else "rejected",
        })
        if verified:
            correction = make_correction(
                root_record_id=record["record_id"],
                subject=value["subject"], predicate=value["predicate"],
                language=value.get("language"), datatype=value.get("datatype"),
                before=value["lexical"], replacement=replacement,
                proposer_route=proposer_route,
                verifier_routes=verifier_routes,
                verifier_qualification_hashes=verifier_qualification_hashes,
            )
            return {
                "state": "verified", "correction": correction,
                "attempts": attempts,
            }
    return {
        "state": "quarantined", "reason": "correction attempts exhausted",
        "attempts": attempts,
    }
