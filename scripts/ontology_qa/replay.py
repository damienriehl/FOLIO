"""Offline verification of ontology QA evidence bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .records import canonical_json, content_hash
from .reporting import validate_artifact_hash, validate_qualification_hash


def _read_json(path: Path, *, canonical: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable artifact {path.name}: {exc}") from exc
    if canonical and raw != canonical_json(value) + b"\n":
        raise ValueError(f"artifact bytes are not canonical: {path.name}")
    return value


def replay_bundle(bundle_path: str | Path, *, report_schema_path: str | Path) -> dict[str, Any]:
    root = Path(bundle_path)
    index = _read_json(root / "index.json", canonical=True)
    report = _read_json(root / "report.json", canonical=True)
    validate_artifact_hash(report)
    Draft202012Validator(
        _read_json(Path(report_schema_path))
    ).validate(report)
    if report["artifact_hash"] != index.get("report_hash"):
        raise ValueError("bundle index report hash mismatch")
    if report["candidate_hash"] != index.get("candidate_hash"):
        raise ValueError("bundle index candidate hash mismatch")
    actual_files = sorted(path.name for path in root.iterdir() if not path.name.startswith(".") and path.name != "index.json")
    indexed_files = sorted(name for name in index.get("files", []) if name != "index.json")
    if actual_files != indexed_files:
        raise ValueError("bundle file set is incomplete or contains unindexed evidence")
    artifacts = {}
    for stage, expected_hash in report["payload"]["stage_hashes"].items():
        artifact = _read_json(root / f"{stage}.json", canonical=True)
        if stage.endswith("_qualification"):
            validate_qualification_hash(artifact)
            if artifact["qualification_hash"] != expected_hash:
                raise ValueError(f"qualification hash mismatch: {stage}")
        else:
            validate_artifact_hash(artifact)
            if artifact["artifact_hash"] != expected_hash:
                raise ValueError(f"stage hash mismatch: {stage}")
            if artifact["candidate_hash"] != report["candidate_hash"]:
                raise ValueError(f"stale candidate binding: {stage}")
        artifacts[stage] = artifact
    if content_hash((root / "candidate.owl").read_bytes()) != report["candidate_hash"]:
        raise ValueError("candidate ontology bytes do not match report")
    if content_hash((root / "baseline.owl").read_bytes()) != report["baseline_hash"]:
        raise ValueError("baseline ontology bytes do not match report")
    parent_hashes = set(report["parent_hashes"])
    if parent_hashes != set(report["payload"]["stage_hashes"].values()):
        raise ValueError("report parent graph is incomplete")
    manifest_ids = {
        item["record_id"] for item in artifacts["manifest"]["payload"]["records"]
    }
    if manifest_ids != set(report["payload"]["record_states"]):
        raise ValueError("final delta and record-state sets differ")
    if (
        artifacts["primary"]["payload"].get("qualification_hash")
        != artifacts["primary_qualification"]["qualification_hash"]
        or artifacts["independent"]["payload"].get("qualification_hash")
        != artifacts["independent_qualification"]["qualification_hash"]
    ):
        raise ValueError("assessment and qualification bindings differ")
    decision = report["payload"]["release_decision"]
    recomputed_pass = (
        report["status"] == "complete"
        and not artifacts["census"]["payload"].get("failures")
        and artifacts["census"]["payload"].get("population_count")
        == artifacts["census"]["payload"].get("inspected_count")
        and all(value == "accepted" for value in report["payload"]["record_states"].values())
        and artifacts["surveillance"]["payload"].get("decision") == "pass"
    )
    if (decision == "merge_gate_passed") != recomputed_pass:
        raise ValueError("release decision does not match replayed evidence")
    return {"verified": True, "release_decision": decision, "report_hash": report["artifact_hash"]}
