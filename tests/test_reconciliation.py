from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.reconcile import reconcile

RID = "a" * 64


def artifact(verdict="pass", confidence=0.99, candidate="candidate", ids=(RID,), qualification="q1"):
    return {
        "status": "complete", "candidate_hash": candidate,
        "payload": {"qualification_hash": qualification, "responses": [
            {"record_id": item, "verdict": verdict, "confidence": confidence}
            for item in ids
        ]},
    }


def test_concordant_high_confidence_pass_is_accepted():
    result = reconcile([RID], artifact(), artifact(qualification="q2"), minimum_confidence=.9, expected_candidate_hash="candidate", expected_primary_qualification="q1", expected_independent_qualification="q2")
    assert result == {"status": "complete", "records": {RID: "accepted"}}


def test_disagreement_or_abstention_quarantines():
    result = reconcile([RID], artifact("pass"), artifact("abstain", qualification="q2"), minimum_confidence=.9, expected_candidate_hash="candidate", expected_primary_qualification="q1", expected_independent_qualification="q2")
    assert result["status"] == "quarantined"


def test_missing_extra_or_duplicate_ids_are_incomplete():
    assert reconcile([RID], artifact(ids=()), artifact(qualification="q2"), minimum_confidence=.9, expected_candidate_hash="candidate", expected_primary_qualification="q1", expected_independent_qualification="q2")["status"] == "incomplete"
    assert reconcile([RID], artifact(ids=(RID, RID)), artifact(qualification="q2"), minimum_confidence=.9, expected_candidate_hash="candidate", expected_primary_qualification="q1", expected_independent_qualification="q2")["status"] == "incomplete"


def test_newer_candidate_fences_stale_results():
    result = reconcile([RID], artifact(candidate="old"), artifact(candidate="old", qualification="q2"), minimum_confidence=.9, expected_candidate_hash="new", expected_primary_qualification="q1", expected_independent_qualification="q2")
    assert result["status"] == "stale"


def test_mismatched_qualification_blocks_reconciliation():
    result = reconcile([RID], artifact(), artifact(qualification="wrong"), minimum_confidence=.9, expected_candidate_hash="candidate", expected_primary_qualification="q1", expected_independent_qualification="q2")
    assert result["status"] == "incomplete"
