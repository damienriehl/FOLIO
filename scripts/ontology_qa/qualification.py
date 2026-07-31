"""Role-specific model qualification and route-independence checks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .records import canonical_json, content_hash

ROLES = {
    "production-primary",
    "production-independent",
    "benchmark-adjudicator",
    "correction-proposer",
    "correction-verifier-1",
    "correction-verifier-2",
}


def create_qualification(
    *,
    role: str,
    route_id: str,
    provider: str,
    requested_model: str,
    actual_model: str,
    reasoning: str,
    corpus_hash: str,
    prompt_hash: str,
    schema_hash: str,
    policy_hash: str,
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
    qualified_at: str,
    valid_until: str,
) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"unsupported qualification role: {role}")
    if requested_model != actual_model:
        raise ValueError("served model does not match pinned model")
    slice_metrics = metrics.get("slice_metrics", [])
    slices_pass = all(
        not item.get("missing_case_ids")
        and item.get("accuracy", 0) >= thresholds["minimum_accuracy"]
        and item.get("defect_recall", 0) >= thresholds["minimum_defect_recall"]
        and item.get("false_accept_rate", 1)
        <= thresholds["maximum_false_accept_rate"]
        for item in slice_metrics
    )
    passes = (
        not metrics.get("missing_case_ids")
        and not metrics.get("unsupported_slices")
        and slices_pass
        and metrics.get("accuracy", 0) >= thresholds["minimum_accuracy"]
        and metrics.get("defect_recall", 0) >= thresholds["minimum_defect_recall"]
        and metrics.get("false_accept_rate", 1) <= thresholds["maximum_false_accept_rate"]
        and (
            not thresholds.get("require_repeat_stability", False)
            or metrics.get("repeat_stability") is True
        )
    )
    metrics = {
        **metrics,
        "qualified_slices": [
            {"family": item["family"], "locale": item["locale"]}
            for item in slice_metrics
            if (
                not item.get("missing_case_ids")
                and item.get("accuracy", 0) >= thresholds["minimum_accuracy"]
                and item.get("defect_recall", 0)
                >= thresholds["minimum_defect_recall"]
                and item.get("false_accept_rate", 1)
                <= thresholds["maximum_false_accept_rate"]
            )
        ],
    }
    body = {
        "role": role, "route_id": route_id, "provider": provider,
        "requested_model": requested_model, "actual_model": actual_model,
        "reasoning": reasoning, "corpus_hash": corpus_hash,
        "prompt_hash": prompt_hash, "schema_hash": schema_hash,
        "policy_hash": policy_hash, "metrics": metrics, "thresholds": thresholds,
        "qualified_at": qualified_at, "valid_until": valid_until,
        "status": "qualified" if passes else "rejected",
    }
    return {"qualification_hash": content_hash(canonical_json(body)), **body}


def validate_role_separation(qualifications: list[dict[str, Any]]) -> None:
    by_role = {item["role"]: item["route_id"] for item in qualifications}
    production = {
        by_role.get("production-primary"),
        by_role.get("production-independent"),
    } - {None}
    benchmark = by_role.get("benchmark-adjudicator")
    if benchmark in production:
        raise ValueError("benchmark adjudication route overlaps a production vote")
    proposer = by_role.get("correction-proposer")
    verifiers = {
        by_role.get("correction-verifier-1"),
        by_role.get("correction-verifier-2"),
    } - {None}
    if proposer in verifiers:
        raise ValueError("correction proposer overlaps a verifier")
    if len(verifiers) == 1 and all(
        role in by_role for role in ("correction-verifier-1", "correction-verifier-2")
    ):
        raise ValueError("correction verifier routes are not independent")


def require_current_qualification(
    qualification: dict[str, Any] | None,
    *,
    expected_role: str,
    expected_route_id: str,
    expected_binding_hashes: dict[str, str],
    now: datetime | None = None,
) -> str:
    if not qualification or qualification.get("status") != "qualified":
        raise ValueError("missing qualified route artifact")
    if qualification.get("role") != expected_role or qualification.get("route_id") != expected_route_id:
        raise ValueError("qualification role or route mismatch")
    for field, expected in expected_binding_hashes.items():
        if qualification.get(field) != expected:
            raise ValueError(f"qualification binding mismatch: {field}")
    current = now or datetime.now(UTC)
    expiry = datetime.fromisoformat(qualification["valid_until"].replace("Z", "+00:00"))
    if current >= expiry:
        raise ValueError("qualification expired")
    body = dict(qualification)
    claimed = body.pop("qualification_hash")
    if content_hash(canonical_json(body)) != claimed:
        raise ValueError("qualification hash mismatch")
    return claimed
