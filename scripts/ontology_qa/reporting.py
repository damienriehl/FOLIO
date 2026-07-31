"""Release-decision reporting and durable artifact-bundle publication."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .records import artifact_envelope, canonical_json, content_hash


def validate_artifact_hash(artifact: dict[str, Any]) -> None:
    body = dict(artifact)
    claimed = body.pop("artifact_hash", None)
    if not claimed or content_hash(canonical_json(body)) != claimed:
        raise ValueError("artifact hash mismatch")


def validate_qualification_hash(qualification: dict[str, Any]) -> None:
    body = dict(qualification)
    claimed = body.pop("qualification_hash", None)
    if not claimed or content_hash(canonical_json(body)) != claimed:
        raise ValueError("qualification hash mismatch")


def build_release_report(
    *,
    manifest: dict[str, Any],
    census: dict[str, Any],
    primary: dict[str, Any],
    independent: dict[str, Any],
    primary_qualification: dict[str, Any],
    independent_qualification: dict[str, Any],
    reconciliation: dict[str, Any],
    surveillance: dict[str, Any],
    run_id: str,
    attempt_id: str,
    policy_hash: str,
    tool_hash: str,
    correction_lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    for artifact in (manifest, census, primary, independent, surveillance):
        validate_artifact_hash(artifact)
    for qualification in (primary_qualification, independent_qualification):
        validate_qualification_hash(qualification)
    candidate_hash = manifest["candidate_hash"]
    stale = any(
        artifact["candidate_hash"] != candidate_hash
        for artifact in (census, primary, independent, surveillance)
    )
    manifest_ids = sorted(
        record["record_id"] for record in manifest["payload"]["records"]
    )
    state_ids = sorted(reconciliation.get("records", {}))
    census_clean = (
        census["status"] == "complete"
        and not census["payload"].get("failures")
        and census["payload"].get("population_count")
        == census["payload"].get("inspected_count")
    )
    provider_complete = primary["status"] == independent["status"] == "complete"
    states_accepted = (
        manifest_ids == state_ids
        and all(value == "accepted" for value in reconciliation.get("records", {}).values())
    )
    surveillance_passed = (
        surveillance["status"] == "complete"
        and surveillance["payload"].get("decision") == "pass"
    )
    qualified = (
        primary_qualification.get("status") == "qualified"
        and independent_qualification.get("status") == "qualified"
        and primary["payload"].get("qualification_hash")
        == primary_qualification["qualification_hash"]
        and independent["payload"].get("qualification_hash")
        == independent_qualification["qualification_hash"]
    )
    passed = (
        not stale and census_clean and provider_complete and states_accepted
        and surveillance_passed and qualified
    )
    stage_hashes = {
        "manifest": manifest["artifact_hash"],
        "census": census["artifact_hash"],
        "primary": primary["artifact_hash"],
        "independent": independent["artifact_hash"],
        "surveillance": surveillance["artifact_hash"],
        "primary_qualification": primary_qualification["qualification_hash"],
        "independent_qualification": independent_qualification["qualification_hash"],
    }
    return artifact_envelope(
        payload={
            "release_decision": "merge_gate_passed" if passed else "blocked",
            "record_count": len(manifest_ids),
            "record_states": reconciliation.get("records", {}),
            "stage_hashes": stage_hashes,
            "correction_lineage": correction_lineage,
            "evidence_summary": {
                "deterministic_compliance": census_clean,
                "cross_provider_concordance": provider_complete and states_accepted,
                "eval_qualification": qualified,
                "legacy_surveillance": surveillance_passed,
                "residual_model_risk": (
                    "Independent automated reviewers can still agree on an incorrect legal interpretation."
                ),
            },
            "claim": "Automated QA evidence; not expert legal certification.",
        },
        run_id=run_id,
        attempt_id=attempt_id,
        parent_hashes=list(stage_hashes.values()),
        baseline_hash=manifest["baseline_hash"],
        candidate_hash=candidate_hash,
        policy_hash=policy_hash,
        tool_hash=tool_hash,
        status="stale" if stale else "complete",
        schema_version="folio-ontology-qa-report/v1",
    )


class ArtifactBundle:
    """Append-only, atomically published local evidence bundle."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def publish_json(self, name: str, artifact: dict[str, Any]) -> Path:
        if not name.replace("-", "").replace("_", "").isalnum():
            raise ValueError("unsafe artifact name")
        validate_artifact_hash(artifact)
        destination = self.root / f"{name}.json"
        if destination.exists():
            if destination.read_bytes() != canonical_json(artifact) + b"\n":
                raise FileExistsError(f"append-only artifact already exists: {name}")
            return destination
        temporary = self.root / f".{name}.tmp"
        temporary.write_bytes(canonical_json(artifact) + b"\n")
        temporary.replace(destination)
        return destination

    def publish_qualification(self, name: str, qualification: dict[str, Any]) -> Path:
        validate_qualification_hash(qualification)
        destination = self.root / f"{name}.json"
        data = canonical_json(qualification) + b"\n"
        if destination.exists() and destination.read_bytes() != data:
            raise FileExistsError(f"append-only qualification already exists: {name}")
        if not destination.exists():
            temporary = self.root / f".{name}.tmp"
            temporary.write_bytes(data)
            temporary.replace(destination)
        return destination

    def snapshot(self, name: str, source: str | Path) -> Path:
        data = Path(source).read_bytes()
        destination = self.root / name
        if destination.exists() and destination.read_bytes() != data:
            raise FileExistsError(f"append-only snapshot already exists: {name}")
        if not destination.exists():
            temporary = self.root / f".{name}.tmp"
            temporary.write_bytes(data)
            temporary.replace(destination)
        return destination

    def publish_index(self, report: dict[str, Any]) -> Path:
        index = {
            "report_hash": report["artifact_hash"],
            "candidate_hash": report["candidate_hash"],
            "files": sorted(path.name for path in self.root.iterdir() if not path.name.startswith(".")),
        }
        destination = self.root / "index.json"
        data = canonical_json(index) + b"\n"
        if destination.exists() and destination.read_bytes() != data:
            raise FileExistsError("bundle index is append-only")
        destination.write_bytes(data)
        return destination
