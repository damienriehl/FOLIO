from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.records import artifact_envelope, content_hash
from ontology_qa.reporting import build_release_report
from ontology_qa.qualification import create_qualification

RID = "a" * 64


def stage(name, candidate_hash, payload, status="complete"):
    return artifact_envelope(
        payload=payload, run_id="run", attempt_id=name, parent_hashes=[],
        baseline_hash="b" * 64, candidate_hash=candidate_hash,
        policy_hash="p", tool_hash="t", status=status,
    )


def qualification(role, route):
    return create_qualification(
        role=role, route_id=route, provider=route.split(":")[0],
        requested_model=route.split(":")[1], actual_model=route.split(":")[1],
        reasoning="high", corpus_hash="a" * 64, prompt_hash="b" * 64,
        schema_hash="c" * 64, policy_hash="d" * 64,
        metrics={"accuracy": 1, "defect_recall": 1, "false_accept_rate": 0, "missing_case_ids": [], "unsupported_slices": []},
        thresholds={"minimum_accuracy": .9, "minimum_defect_recall": .95, "maximum_false_accept_rate": .02},
        qualified_at="2026-07-30T00:00:00Z", valid_until="2026-08-30T00:00:00Z",
    )


def evidence(candidate_hash="c" * 64, state="accepted"):
    primary_qualification = qualification("production-primary", "openai:gpt-5.6-sol")
    independent_qualification = qualification("production-independent", "google:gemini-3.5-flash")
    manifest = stage("manifest", candidate_hash, {
        "records": [{"record_id": RID}], "record_count": 1,
        "unrelated_semantic_drift": [],
    })
    census = stage("census", candidate_hash, {
        "failures": [], "population_count": 1, "inspected_count": 1,
    })
    primary = stage("primary", candidate_hash, {
        "provider": "openai", "model": "gpt-5.6-sol",
        "actual_model": "gpt-5.6-sol",
        "qualification_hash": primary_qualification["qualification_hash"],
        "responses": [{"record_id": RID, "verdict": "pass", "confidence": .99}],
    })
    independent = stage("independent", candidate_hash, {
        "provider": "google", "model": "gemini-3.5-flash",
        "actual_model": "gemini-3.5-flash",
        "qualification_hash": independent_qualification["qualification_hash"],
        "responses": [{"record_id": RID, "verdict": "pass", "confidence": .99}],
    })
    surveillance = stage("surveillance", candidate_hash, {"decision": "pass"})
    reconciliation = {"status": "complete", "records": {RID: state}}
    return manifest, census, primary, independent, reconciliation, surveillance, primary_qualification, independent_qualification


def report_for(parts):
    manifest, census, primary, independent, reconciliation, surveillance, primary_qualification, independent_qualification = parts
    return build_release_report(
        manifest=manifest, census=census, primary=primary,
        independent=independent, reconciliation=reconciliation,
        primary_qualification=primary_qualification,
        independent_qualification=independent_qualification,
        surveillance=surveillance, run_id="run", attempt_id="report",
        policy_hash="p", tool_hash="t",
    )


def test_fully_concordant_artifacts_reach_merge_gate():
    report = report_for(evidence())
    assert report["payload"]["release_decision"] == "merge_gate_passed"
    assert report["status"] == "complete"


def test_quarantine_or_incomplete_stage_blocks():
    parts = list(evidence(state="quarantined"))
    assert report_for(parts)["payload"]["release_decision"] == "blocked"
    parts = list(evidence())
    parts[2] = stage("primary", "c" * 64, {
        "qualification_hash": parts[6]["qualification_hash"], "responses": [],
    }, status="incomplete")
    assert report_for(parts)["payload"]["release_decision"] == "blocked"


def test_stale_candidate_hash_blocks_and_marks_report_stale():
    parts = list(evidence())
    parts[3] = stage("independent", "d" * 64, {
        "qualification_hash": "2" * 64, "responses": [{"record_id": RID}],
    })
    report = report_for(parts)
    assert report["status"] == "stale"
    assert report["payload"]["release_decision"] == "blocked"


def test_report_uses_conservative_legal_claim():
    report = report_for(evidence())
    assert report["payload"]["claim"] == "Automated QA evidence; not expert legal certification."
    assert "still agree on an incorrect" in report["payload"]["evidence_summary"]["residual_model_risk"]
