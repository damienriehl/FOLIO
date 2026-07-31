"""Blind provider dispatch and immutable assessment artifacts."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from .providers.base import ProviderAdapter, ProviderError, ReviewRequest
from .records import artifact_envelope, canonical_json, content_hash


def run_blind_review(
    adapter: ProviderAdapter,
    *,
    records: list[dict[str, Any]],
    prompt: str,
    schema: dict[str, Any],
    context_hash: str,
    qualification_hash: str,
    run_id: str,
    attempt_id: str,
    baseline_hash: str,
    candidate_hash: str,
    policy_hash: str,
    tool_hash: str,
    max_retries: int = 2,
) -> dict[str, Any]:
    request_data = {
        "record_ids": sorted(record["record_id"] for record in records),
        "context_hash": context_hash,
        "prompt_hash": content_hash(prompt),
        "schema_hash": content_hash(canonical_json(schema)),
        "qualification_hash": qualification_hash,
        "provider": adapter.provider,
        "model": adapter.model,
    }
    request = ReviewRequest(
        request_id=content_hash(canonical_json(request_data)),
        model=adapter.model,
        prompt=prompt,
        records=tuple(records),
        schema=schema,
        context_hash=context_hash,
    )
    receipt = None
    for retry in range(max_retries + 1):
        try:
            receipt = adapter.assess(request)
            break
        except ProviderError as exc:
            if not exc.transient or retry == max_retries:
                return artifact_envelope(
                    payload={**request_data, "responses": [], "error": str(exc), "retry_count": retry},
                    run_id=run_id, attempt_id=attempt_id, parent_hashes=[qualification_hash],
                    baseline_hash=baseline_hash, candidate_hash=candidate_hash,
                    policy_hash=policy_hash, tool_hash=tool_hash, status="incomplete",
                )
    assert receipt is not None
    validator = Draft202012Validator(schema)
    try:
        for response in receipt.responses:
            validator.validate(response)
    except ValidationError as exc:
        return artifact_envelope(
            payload={**request_data, "responses": [], "error": f"schema validation failed: {exc.message}", "retry_count": retry},
            run_id=run_id, attempt_id=attempt_id, parent_hashes=[qualification_hash],
            baseline_hash=baseline_hash, candidate_hash=candidate_hash,
            policy_hash=policy_hash, tool_hash=tool_hash, status="incomplete",
        )
    expected = request_data["record_ids"]
    actual = sorted(response["record_id"] for response in receipt.responses)
    if actual != expected or len(actual) != len(set(actual)):
        status, error = "incomplete", "provider result IDs do not exactly match manifest"
    else:
        status, error = "complete", None
    return artifact_envelope(
        payload={
            **request_data,
            "actual_model": receipt.actual_model,
            "responses": list(receipt.responses),
            "retry_count": retry,
            "error": error,
        },
        run_id=run_id, attempt_id=attempt_id, parent_hashes=[qualification_hash],
        baseline_hash=baseline_hash, candidate_hash=candidate_hash,
        policy_hash=policy_hash, tool_hash=tool_hash, status=status,
    )
