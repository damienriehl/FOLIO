"""Offline verification of ontology QA evidence bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from .evals import corpus_identity
from .reconcile import reconcile
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
    primary_q = artifacts["primary_qualification"]
    independent_q = artifacts["independent_qualification"]
    if primary_q.get("status") != "qualified" or independent_q.get("status") != "qualified":
        raise ValueError("release uses an unqualified model route")
    if (
        artifacts["primary"].get("status") != "complete"
        or artifacts["independent"].get("status") != "complete"
    ):
        raise ValueError("release uses incomplete model assessments")
    for assessment, qualification in (
        (artifacts["primary"], primary_q),
        (artifacts["independent"], independent_q),
    ):
        if (
            assessment["payload"].get("provider") != qualification["provider"]
            or assessment["payload"].get("model") != qualification["requested_model"]
            or assessment["payload"].get("actual_model") != qualification["actual_model"]
        ):
            raise ValueError("assessment route differs from qualification")

    model_policy_path = root / "model-policy.yaml"
    if model_policy_path.exists():
        review_policy_path = root / "review-policy.yaml"
        expected_policy_hash = content_hash(
            model_policy_path.read_bytes() + review_policy_path.read_bytes()
        )
        if expected_policy_hash != report["policy_hash"]:
            raise ValueError("snapshotted policy hash mismatch")
        model_policy = yaml.safe_load(model_policy_path.read_text(encoding="utf-8"))
        minimum_confidence = float(model_policy["minimum_confidence"])
        schema = _read_json(root / "review-schema.json")
        schema_hash = content_hash(canonical_json(schema))
        prompt_hash = content_hash(canonical_json({
            family: (root / name).read_text(encoding="utf-8")
            for family, name in (
                ("definition", "prompt-definition.md"),
                ("example", "prompt-example.md"),
                ("translation", "prompt-translation.md"),
                ("correction-proposal", "prompt-correction-proposal.md"),
                ("correction-verification", "prompt-correction-verification.md"),
            )
        }))
        corpus_hash = corpus_identity(
            [root / "eval-cases.jsonl", root / "eval-held-out.jsonl"]
        )
        for qualification in (primary_q, independent_q):
            if (
                qualification["schema_hash"] != schema_hash
                or qualification["prompt_hash"] != prompt_hash
                or qualification["corpus_hash"] != corpus_hash
                or qualification["policy_hash"] != report["policy_hash"]
            ):
                raise ValueError("qualification inputs differ from snapshots")
        tool_manifest = _read_json(root / "tool-manifest.json", canonical=True)
        claimed_tool_hash = tool_manifest.pop("tool_hash", None)
        if (
            content_hash(canonical_json(tool_manifest)) != claimed_tool_hash
            or claimed_tool_hash != report["tool_hash"]
        ):
            raise ValueError("tool manifest hash mismatch")
    else:
        minimum_confidence = 0.9

    reconstructed = reconcile(
        sorted(manifest_ids), artifacts["primary"], artifacts["independent"],
        minimum_confidence=minimum_confidence,
        expected_candidate_hash=report["candidate_hash"],
        expected_primary_qualification=primary_q["qualification_hash"],
        expected_independent_qualification=independent_q["qualification_hash"],
    )
    if reconstructed["records"] != report["payload"]["record_states"]:
        raise ValueError("record states do not match provider assessments")
    decision = report["payload"]["release_decision"]
    recomputed_pass = (
        report["status"] == "complete"
        and not artifacts["census"]["payload"].get("failures")
        and artifacts["census"]["payload"].get("population_count")
        == artifacts["census"]["payload"].get("inspected_count")
        and all(value == "accepted" for value in report["payload"]["record_states"].values())
        and artifacts["surveillance"]["payload"].get("decision") == "pass"
        and primary_q["status"] == independent_q["status"] == "qualified"
        and reconstructed["status"] == "complete"
    )
    if (decision == "merge_gate_passed") != recomputed_pass:
        raise ValueError("release decision does not match replayed evidence")
    return {"verified": True, "release_decision": decision, "report_hash": report["artifact_hash"]}
