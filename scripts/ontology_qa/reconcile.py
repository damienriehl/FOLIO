"""Deterministic exact-set reconciliation for blind assessments."""

from __future__ import annotations

from typing import Any


def reconcile(
    record_ids: list[str],
    primary: dict[str, Any],
    independent: dict[str, Any],
    *,
    minimum_confidence: float,
    expected_candidate_hash: str,
    expected_primary_qualification: str,
    expected_independent_qualification: str,
) -> dict[str, Any]:
    expected = sorted(record_ids)
    if primary["candidate_hash"] != expected_candidate_hash or independent["candidate_hash"] != expected_candidate_hash:
        return {"status": "stale", "records": {}}
    if primary["status"] != "complete" or independent["status"] != "complete":
        return {"status": "incomplete", "records": {}}
    if (
        primary["payload"].get("qualification_hash") != expected_primary_qualification
        or independent["payload"].get("qualification_hash") != expected_independent_qualification
    ):
        return {"status": "incomplete", "records": {}}
    left_responses = primary["payload"]["responses"]
    right_responses = independent["payload"]["responses"]
    left = {item["record_id"]: item for item in left_responses}
    right = {item["record_id"]: item for item in right_responses}
    if (
        sorted(left) != expected
        or sorted(right) != expected
        or len(left_responses) != len(left)
        or len(right_responses) != len(right)
    ):
        return {"status": "incomplete", "records": {}}
    states = {}
    for record_id in expected:
        a, b = left[record_id], right[record_id]
        if a["verdict"] == b["verdict"] == "pass" and min(a["confidence"], b["confidence"]) >= minimum_confidence:
            state = "accepted"
        elif a["verdict"] == b["verdict"] == "defect":
            state = "defect_confirmed"
        else:
            state = "quarantined"
        states[record_id] = state
    overall = "complete" if all(value in {"accepted", "defect_confirmed"} for value in states.values()) else "quarantined"
    return {"status": overall, "records": states}
