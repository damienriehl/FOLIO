from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.records import content_hash
from ontology_qa.replay import replay_bundle
from ontology_qa.reporting import ArtifactBundle
from test_hydration_qa_pipeline import evidence, report_for

ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "schemas/ontology-qa-report.schema.json"


def bundle(tmp_path: Path):
    candidate = tmp_path / "source-candidate.owl"
    baseline = tmp_path / "source-baseline.owl"
    candidate.write_text("<candidate/>", encoding="utf-8")
    baseline.write_text("<baseline/>", encoding="utf-8")
    candidate_hash = content_hash(candidate.read_bytes())
    parts = evidence(candidate_hash)
    baseline_hash = content_hash(baseline.read_bytes())
    # Bind every stage and the report to the exact baseline snapshot.
    rebound = []
    from ontology_qa.records import artifact_envelope
    for artifact in (parts[0], parts[1], parts[2], parts[3], parts[5]):
        rebound.append(artifact_envelope(
            payload=artifact["payload"], run_id=artifact["run_id"],
            attempt_id=artifact["attempt_id"], parent_hashes=artifact["parent_hashes"],
            baseline_hash=baseline_hash, candidate_hash=artifact["candidate_hash"],
            policy_hash=artifact["policy_hash"], tool_hash=artifact["tool_hash"],
            status=artifact["status"], schema_version=artifact["schema_version"],
        ))
    parts = (rebound[0], rebound[1], rebound[2], rebound[3], parts[4], rebound[4], parts[6], parts[7])
    report = report_for(parts)
    target = tmp_path / "bundle"
    store = ArtifactBundle(target)
    for name, artifact in zip(
        ("manifest", "census", "primary", "independent", "surveillance"),
        (parts[0], parts[1], parts[2], parts[3], parts[5]),
    ):
        store.publish_json(name, artifact)
    store.publish_qualification("primary_qualification", parts[6])
    store.publish_qualification("independent_qualification", parts[7])
    store.publish_json("report", report)
    store.snapshot("candidate.owl", candidate)
    store.snapshot("baseline.owl", baseline)
    store.publish_index(report)
    return target


def test_clean_bundle_replays_without_provider_access(tmp_path):
    result = replay_bundle(bundle(tmp_path), report_schema_path=SCHEMA)
    assert result["verified"] is True
    assert result["release_decision"] == "merge_gate_passed"


@pytest.mark.parametrize("name", ["manifest.json", "primary.json", "report.json", "candidate.owl"])
def test_tampered_evidence_fails_replay(tmp_path, name):
    target = bundle(tmp_path)
    path = target / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        replay_bundle(target, report_schema_path=SCHEMA)


def test_missing_stage_fails_replay(tmp_path):
    target = bundle(tmp_path)
    (target / "surveillance.json").unlink()
    with pytest.raises(ValueError):
        replay_bundle(target, report_schema_path=SCHEMA)


def test_append_only_bundle_rejects_overwrite(tmp_path):
    target = bundle(tmp_path)
    store = ArtifactBundle(target)
    artifact = json.loads((target / "manifest.json").read_text())
    artifact["payload"]["record_count"] = 99
    with pytest.raises(ValueError, match="hash"):
        store.publish_json("manifest", artifact)


def test_cli_replays_complete_bundle(tmp_path):
    target = bundle(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_ontology_hydration_qa.py"),
            "--bundle", str(target), "--replay",
            "--report-schema", str(SCHEMA),
        ],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["verified"] is True
