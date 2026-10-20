from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from ontology_qa.correction_pipeline import converge_correction

RID = "a" * 64
RECORD = {
    "record_id": RID,
    "after": {
        "subject": "https://example.test/C",
        "predicate": "http://www.w3.org/2004/02/skos/core#definition",
        "object_kind": "literal", "language": "en", "datatype": None,
        "lexical": "A party must not appeal.",
    },
}


def proposal(replacement):
    return lambda record, attempt: {
        "record_id": RID, "verdict": "defect", "confidence": .99,
        "proposed_replacement": replacement,
    }


def vote(verdict="pass", confidence=.99):
    return lambda record, attempt: {
        "record_id": RID, "verdict": verdict, "confidence": confidence,
        "proposed_replacement": None,
    }


def kwargs():
    return {
        "proposer_route": "openai:gpt-5.6-sol",
        "verifier_routes": [
            "google:gemini-3.5-flash", "openai:gpt-5.6-terra",
        ],
        "verifier_qualification_hashes": ["b" * 64, "c" * 64],
        "minimum_confidence": .9,
    }


def test_exact_candidate_requires_two_blind_high_confidence_votes():
    result = converge_correction(
        RECORD, proposer=proposal("A party may appeal."),
        verifier_1=vote(), verifier_2=vote(), **kwargs(),
    )
    assert result["state"] == "verified"
    assert result["correction"]["replacement"] == "A party may appeal."
    assert result["correction"]["proposer_route"] not in (
        result["correction"]["verifier_routes"]
    )


def test_second_rejection_is_terminal_quarantine():
    replacements = iter([
        "A party may appeal.", "A party has permission to appeal.",
    ])
    result = converge_correction(
        RECORD,
        proposer=lambda record, attempt: {
            "record_id": RID, "verdict": "defect", "confidence": .99,
            "proposed_replacement": next(replacements),
        },
        verifier_1=vote("defect"), verifier_2=vote(), **kwargs(),
    )
    assert result["state"] == "quarantined"
    assert len(result["attempts"]) == 2


def test_repeated_candidate_cycle_quarantines_without_extra_vote():
    calls = []

    def verifier(record, attempt):
        calls.append(attempt)
        return vote("defect")(record, attempt)

    result = converge_correction(
        RECORD, proposer=proposal("A party may appeal."),
        verifier_1=verifier, verifier_2=vote(), **kwargs(),
    )
    assert result["state"] == "quarantined"
    assert result["reason"] == "correction cycle"
    assert calls == [1]
