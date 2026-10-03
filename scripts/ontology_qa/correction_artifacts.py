"""Shared correction response-set checks and canonical publication helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .records import canonical_json


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
    *,
    expected_count: int | None = None,
) -> None:
    expected = {record["record_id"] for record in records}
    actual = {response["record_id"] for response in responses}
    if expected_count is None:
        expected_count = len(expected)
    if actual != expected or expected_count != len(responses):
        raise ValueError("assessment response set is incomplete")


def _canonical_json_bytes(value: Any) -> bytes:
    return canonical_json(value) + b"\n"


def _write_once(path: Path, value: Any) -> None:
    data = _canonical_json_bytes(value)
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"append-only output exists: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _check_write_once(path: Path, value: Any) -> None:
    data = _canonical_json_bytes(value)
    if path.exists() and path.read_bytes() != data:
        raise FileExistsError(f"append-only output exists: {path}")
