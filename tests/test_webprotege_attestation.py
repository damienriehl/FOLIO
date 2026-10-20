from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.attestation import build_acceptance_predicate, verify_acceptance_handoff
from ontology_qa.records import content_hash
from test_evidence_replay import bundle

ROOT = Path(__file__).parents[1]


def accepted(tmp_path):
    evidence = bundle(tmp_path)
    import json
    report = json.loads((evidence / "report.json").read_text())
    candidate = evidence / "candidate.owl"
    digest = "sha256:" + content_hash(b"bundle archive")
    predicate = build_acceptance_predicate(
        repository="owner/folio", workflow_ref="owner/folio/.github/workflows/ontology-hydration-qa.yml@refs/heads/main",
        commit_sha="a" * 40, tree_sha="b" * 40, run_id="1", run_attempt="1",
        report=report, evidence_bundle_digest=digest,
        expires_at="2027-01-01T00:00:00Z",
    )
    return evidence, candidate, digest, predicate


def verify(parts, **changes):
    evidence, candidate, digest, predicate = parts
    values = dict(
        expected_repository="owner/folio",
        expected_candidate_repository="owner/folio",
        expected_workflow_ref="owner/folio/.github/workflows/ontology-hydration-qa.yml@refs/heads/main",
        expected_commit_sha="a" * 40, expected_tree_sha="b" * 40,
        candidate_path=candidate, bundle_path=evidence,
        report_schema_path=ROOT / "schemas/ontology-qa-report.schema.json",
        bundle_digest=digest, now=datetime(2026, 8, 1, tzinfo=UTC),
    )
    values.update(changes)
    return verify_acceptance_handoff(predicate, **values)


def test_exact_attested_candidate_and_bundle_pass(tmp_path):
    assert verify(accepted(tmp_path))["verified"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [("expected_commit_sha", "c" * 40), ("expected_tree_sha", "d" * 40), ("expected_workflow_ref", "other")],
)
def test_wrong_commit_tree_or_workflow_is_rejected(tmp_path, field, value):
    with pytest.raises(ValueError, match="identity"):
        verify(accepted(tmp_path), **{field: value})


def test_tampered_bundle_or_candidate_is_rejected(tmp_path):
    parts = accepted(tmp_path)
    with pytest.raises(ValueError, match="digest"):
        verify(parts, bundle_digest="sha256:wrong")
    parts[1].write_bytes(b"changed")
    with pytest.raises(ValueError, match="candidate"):
        verify(parts)


def test_expired_attestation_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="expired"):
        verify(accepted(tmp_path), now=datetime(2028, 1, 1, tzinfo=UTC))
