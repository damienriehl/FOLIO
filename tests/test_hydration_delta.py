from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from ontology_qa.delta import build_hydration_manifest, manifest_bytes


PREFIX = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:skos="http://www.w3.org/2004/02/skos/core#">
<rdf:Description rdf:about="https://example.test/C">
"""
SUFFIX = "</rdf:Description></rdf:RDF>"


def owl(*values: str) -> str:
    return PREFIX + "".join(values) + SUFFIX


def literal(text: str, lang: str = "en") -> str:
    return f'<skos:altLabel xml:lang="{lang}">{text}</skos:altLabel>'


def write_pair(tmp_path: Path, before: str, after: str) -> tuple[Path, Path]:
    baseline, candidate = tmp_path / "before.owl", tmp_path / "after.owl"
    baseline.write_text(before, encoding="utf-8")
    candidate.write_text(after, encoding="utf-8")
    return baseline, candidate


def manifest(tmp_path: Path, before: str, after: str) -> dict:
    baseline, candidate = write_pair(tmp_path, before, after)
    return build_hydration_manifest(
        baseline, candidate, run_id="run-1", attempt_id="attempt-1"
    )


@pytest.mark.parametrize(
    ("before", "after", "change"),
    [
        (owl(), owl(literal("Appeal")), "added"),
        (owl(literal("Appeal")), owl(), "removed"),
        (owl(literal("Appeal", "en")), owl(literal("Appeal", "fr")), "retagged"),
        (owl(literal("Appeal")), owl(literal("Appellate review")), "replaced"),
    ],
)
def test_classifies_annotation_changes(tmp_path, before, after, change):
    result = manifest(tmp_path, before, after)
    assert [record["change"] for record in result["payload"]["records"]] == [change]


def test_serialization_only_change_is_empty(tmp_path):
    before = owl(literal("A") + literal("B"))
    after = owl(literal("B") + literal("A"))
    assert manifest(tmp_path, before, after)["payload"]["records"] == []


def test_revision_id_binds_candidate_value(tmp_path):
    first = manifest(tmp_path, owl(literal("A")), owl(literal("B")))
    second = manifest(tmp_path, owl(literal("A")), owl(literal("C")))
    assert first["payload"]["records"][0]["record_id"] != second["payload"]["records"][0]["record_id"]


def test_multivalued_changes_are_not_paired_ambiguously(tmp_path):
    result = manifest(
        tmp_path,
        owl(literal("A") + literal("B")),
        owl(literal("C") + literal("D")),
    )
    assert sorted(record["change"] for record in result["payload"]["records"]) == [
        "added", "added", "removed", "removed"
    ]


def test_input_hash_mismatch_fails(tmp_path):
    baseline, candidate = write_pair(tmp_path, owl(), owl(literal("A")))
    with pytest.raises(ValueError, match="baseline hash"):
        build_hydration_manifest(
            baseline,
            candidate,
            run_id="run-1",
            attempt_id="attempt-1",
            baseline_sha="0" * 64,
        )


def test_manifest_is_byte_stable_and_self_hashed(tmp_path):
    baseline, candidate = write_pair(tmp_path, owl(), owl(literal("A")))
    first = build_hydration_manifest(
        baseline, candidate, run_id="run-1", attempt_id="attempt-1"
    )
    second = build_hydration_manifest(
        baseline, candidate, run_id="run-1", attempt_id="attempt-1"
    )
    assert manifest_bytes(first) == manifest_bytes(second)
    envelope = dict(first)
    artifact_hash = envelope.pop("artifact_hash")
    expected = hashlib.sha256(
        json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert artifact_hash == expected
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas/hydration-delta.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(first)
