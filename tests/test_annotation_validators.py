from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.validators import validate_ontology

ROOT = Path(__file__).parents[1]


def document(body: str) -> str:
    return f"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
 xmlns:skos="http://www.w3.org/2004/02/skos/core#">
<rdf:Description rdf:about="https://example.test/C">{body}</rdf:Description>
</rdf:RDF>"""


def run(tmp_path: Path, body: str) -> dict:
    ontology = tmp_path / "ontology.owl"
    ontology.write_text(document(body), encoding="utf-8")
    return validate_ontology(
        ontology,
        policy_path=ROOT / "qa/ontology/review-policy.yaml",
        shapes_path=ROOT / "qa/ontology/shapes.ttl",
    )


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("", "empty_annotation"),
        ("   ", "empty_annotation"),
        ("NULL", "sentinel_annotation"),
        ("['appeal', 'review']", "serialized_container"),
    ],
)
def test_mechanical_definition_defects_fail(tmp_path, value, code):
    result = run(tmp_path, f"<skos:definition>{value}</skos:definition>")
    assert code in {item["code"] for item in result["failures"]}
    assert result["population_count"] == result["inspected_count"] == 1


def test_invalid_language_tag_fails(tmp_path):
    result = run(tmp_path, '<skos:altLabel xml:lang="not_a_tag">Appeal</skos:altLabel>')
    assert "invalid_language_tag" in {item["code"] for item in result["failures"]}


def test_resource_value_fails_by_policy(tmp_path):
    result = run(tmp_path, '<skos:definition rdf:resource="https://example.test/D"/>')
    assert "unsupported_object_kind" in {item["code"] for item in result["failures"]}


def test_ambiguous_lexical_signals_route_to_review(tmp_path):
    result = run(
        tmp_path,
        '<rdfs:label xml:lang="en">Appeal</rdfs:label>'
        '<skos:altLabel xml:lang="en">Appeal</skos:altLabel>'
        '<skos:altLabel xml:lang="ru-XX">Appeal</skos:altLabel>',
    )
    codes = {item["code"] for item in result["semantic_review_risks"]}
    assert {"base_label_duplicate", "script_mismatch", "unusual_language_tag"} <= codes


def test_cardinality_violation_fails(tmp_path):
    result = run(
        tmp_path,
        "<skos:prefLabel>A</skos:prefLabel><skos:prefLabel>B</skos:prefLabel>",
    )
    assert "cardinality_violation" in {item["code"] for item in result["failures"]}


def test_malformed_xml_is_counted_as_failed_input(tmp_path):
    ontology = tmp_path / "broken.owl"
    ontology.write_text("<rdf:RDF>", encoding="utf-8")
    result = validate_ontology(
        ontology,
        policy_path=ROOT / "qa/ontology/review-policy.yaml",
        shapes_path=ROOT / "qa/ontology/shapes.ttl",
    )
    assert result["status"] == "failed"
    assert result["failures"][0]["code"] == "malformed_xml"


def test_clean_annotation_passes_and_is_fully_counted(tmp_path):
    result = run(tmp_path, '<skos:definition xml:lang="en">A legal definition.</skos:definition>')
    assert result["status"] == "complete"
    assert result["population_count"] == result["inspected_count"] == 1
