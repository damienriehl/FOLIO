from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.correction_evidence import verify_correction_lineage
from ontology_qa.corrections import apply_correction_batch, make_correction
from ontology_qa.qualification import create_qualification
from ontology_qa.records import canonical_json, content_hash

ROOT = Path(__file__).parents[1]


def _qualification(role: str, route: str):
    return create_qualification(
        role=role, route_id=route, provider=route.split(":")[0],
        requested_model=route.split(":")[1],
        actual_model=route.split(":")[1], reasoning="high",
        corpus_hash="a" * 64, prompt_hash="b" * 64,
        schema_hash="c" * 64, policy_hash="d" * 64,
        metrics={
            "accuracy": 1, "defect_recall": 1, "false_accept_rate": 0,
            "missing_case_ids": [], "unsupported_slices": [],
        },
        thresholds={
            "minimum_accuracy": .9, "minimum_defect_recall": .95,
            "maximum_false_accept_rate": .02,
        },
        qualified_at="2026-07-30T00:00:00Z",
        valid_until="2026-08-30T00:00:00Z",
    )


def _fixture(tmp_path: Path):
    source = tmp_path / "source.owl"
    candidate = tmp_path / "candidate.owl"
    source.write_text(
        '<?xml version="1.0"?><rdf:RDF '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:skos="http://www.w3.org/2004/02/skos/core#">'
        '<rdf:Description rdf:about="https://example.test/C">'
        '<skos:definition xml:lang="en">Bad</skos:definition>'
        '</rdf:Description></rdf:RDF>',
        encoding="utf-8",
    )
    correction = make_correction(
        root_record_id="a" * 64, subject="https://example.test/C",
        predicate="http://www.w3.org/2004/02/skos/core#definition",
        language="en", datatype=None, before="Bad", replacement="Good",
        proposer_route="openai:proposer",
        verifier_routes=["google:verifier", "openai:verifier"],
        verifier_qualification_hashes=["1" * 64, "2" * 64],
    )
    transaction = apply_correction_batch(source, candidate, [correction])
    qualifications = {
        "production-primary": _qualification(
            "production-primary", "openai:primary"
        ),
        "production-independent": _qualification(
            "production-independent", "google:independent"
        ),
        "correction-proposer": _qualification(
            "correction-proposer", "openai:proposer"
        ),
        "correction-verifier-1": _qualification(
            "correction-verifier-1", "google:verifier"
        ),
        "correction-verifier-2": _qualification(
            "correction-verifier-2", "openai:verifier"
        ),
    }
    response = {
        "record_id": "a" * 64, "verdict": "pass", "confidence": .99,
    }
    body = {
        "schema_version": 1,
        "source_hash": content_hash(source.read_bytes()),
        "candidate_hash": content_hash(candidate.read_bytes()),
        "qualifications": qualifications,
        "convergences": [{
            "record_id": "a" * 64, "state": "verified",
            "correction": correction,
        }],
        "transaction": transaction,
        "rereviews": {
            "production-primary": [response],
            "production-independent": [response],
        },
    }
    evidence = {
        "evidence_hash": content_hash(canonical_json(body)), **body,
    }
    ledger_path = tmp_path / "ledger.json"
    evidence_path = tmp_path / "evidence.json"
    ledger_path.write_bytes(canonical_json([correction]) + b"\n")
    evidence_path.write_bytes(canonical_json(evidence) + b"\n")
    return source, candidate, ledger_path, evidence_path


def test_correction_lineage_replays_to_exact_candidate(tmp_path):
    source, candidate, ledger, evidence = _fixture(tmp_path)
    result = verify_correction_lineage(
        source_path=source, candidate_path=candidate,
        ledger_path=ledger, evidence_path=evidence,
        schema_path=ROOT / "schemas/ontology-correction.schema.json",
        minimum_confidence=.9,
    )
    assert result["correction_count"] == 1
    assert result["candidate_hash"] == content_hash(candidate.read_bytes())


def test_same_provider_final_votes_fail_closed(tmp_path):
    source, candidate, ledger, evidence = _fixture(tmp_path)
    value = json.loads(evidence.read_text())
    qualification = value["qualifications"]["production-independent"]
    qualification["provider"] = "openai"
    body = dict(qualification)
    body.pop("qualification_hash")
    qualification["qualification_hash"] = content_hash(canonical_json(body))
    evidence_body = dict(value)
    evidence_body.pop("evidence_hash")
    value["evidence_hash"] = content_hash(canonical_json(evidence_body))
    evidence.write_bytes(canonical_json(value) + b"\n")
    with pytest.raises(ValueError, match="cross-provider"):
        verify_correction_lineage(
            source_path=source, candidate_path=candidate,
            ledger_path=ledger, evidence_path=evidence,
            schema_path=ROOT / "schemas/ontology-correction.schema.json",
            minimum_confidence=.9,
        )


def test_tampered_ledger_fails_replay(tmp_path):
    source, candidate, ledger, evidence = _fixture(tmp_path)
    value = json.loads(ledger.read_text())
    value[0]["replacement"] = "Different"
    ledger.write_bytes(canonical_json(value) + b"\n")
    with pytest.raises(ValueError):
        verify_correction_lineage(
            source_path=source, candidate_path=candidate,
            ledger_path=ledger, evidence_path=evidence,
            schema_path=ROOT / "schemas/ontology-correction.schema.json",
            minimum_confidence=.9,
        )
