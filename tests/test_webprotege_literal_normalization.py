"""RDF 1.1 string equivalence in the WebProtégé comparison, retaining XML types."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from rdflib import Literal
from rdflib.namespace import XSD

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from generate_webprotege_merge import apply_changes, compute_semantic_diff

SUBJECT = "https://folio.openlegalstandard.org/Test"
TYPED = ' rdf:datatype="http://www.w3.org/2001/XMLSchema#string"'


def ontology(body: str) -> str:
    return f'''<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:owl="http://www.w3.org/2002/07/owl#"
 xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
 xmlns:skos="http://www.w3.org/2004/02/skos/core#">
<owl:Class rdf:about="{SUBJECT}">
{body}
</owl:Class>
</rdf:RDF>'''


def compare(tmp_path: Path, gh: str, wp: str):
    path = tmp_path / "candidate.owl"
    path.write_text(gh, encoding="utf-8")
    return compute_semantic_diff(str(path), wp)


@pytest.mark.parametrize("predicate", [
    "skos:definition", "skos:altLabel", "skos:hiddenLabel", "rdfs:label", "skos:notation",
])
@pytest.mark.parametrize("gh_attr,wp_attr", [("", TYPED), (TYPED, "")])
def test_plain_and_typed_string_have_no_diff(tmp_path, predicate, gh_attr, wp_attr):
    gh = ontology(f'<{predicate}{gh_attr}>x</{predicate}>')
    wp = ontology(f'<{predicate}{wp_attr}>x</{predicate}>')
    diff = compare(tmp_path, gh, wp)
    assert not diff.new_alt_labels
    assert not diff.definition_updates
    assert not diff.definition_additions
    assert not diff.label_normalizations
    assert not diff.removed_labels
    assert not diff.removals
    assert apply_changes(wp, diff, gh) == wp


def test_different_definition_still_has_diff(tmp_path):
    gh = ontology('<skos:definition>New</skos:definition>')
    wp = ontology(f'<skos:definition{TYPED}>Old</skos:definition>')
    diff = compare(tmp_path, gh, wp)
    assert diff.definition_updates[SUBJECT] == [Literal("New")]
    assert "New" in apply_changes(wp, diff, gh)


@pytest.mark.parametrize("gh_attr,wp_attr", [
    (' xml:lang="en"', ""), ("", ' xml:lang="en"'),
    (' xml:lang="en"', TYPED), (' xml:lang="en"', ' xml:lang="fr"'),
])
@pytest.mark.parametrize("predicate", ["skos:definition", "skos:altLabel"])
def test_language_tags_stay_distinct(tmp_path, predicate, gh_attr, wp_attr):
    diff = compare(
        tmp_path,
        ontology(f'<{predicate}{gh_attr}>x</{predicate}>'),
        ontology(f'<{predicate}{wp_attr}>x</{predicate}>'),
    )
    if predicate == "skos:definition":
        assert SUBJECT in diff.definition_updates
    else:
        assert SUBJECT in diff.new_alt_labels
    assert diff.removals


@pytest.mark.parametrize("predicate", ["skos:definition", "skos:altLabel"])
def test_new_typed_string_keeps_original_literal_and_output_format(tmp_path, predicate):
    tag = f'<{predicate}{TYPED}>Added</{predicate}>'
    gh = ontology(tag)
    wp = ontology("")
    diff = compare(tmp_path, gh, wp)
    values = diff.definition_additions if predicate == "skos:definition" else diff.new_alt_labels
    assert values[SUBJECT] == [Literal("Added", datatype=XSD.string)]
    # Definitions retain their datatype; altLabels use the existing plain XML form.
    expected = tag if predicate == "skos:definition" else "<skos:altLabel>Added</skos:altLabel>"
    assert expected in apply_changes(wp, diff, gh)


def test_normalization_recognizes_typed_label_and_notation(tmp_path):
    gh = ontology(f'<rdfs:label{TYPED}>Test</rdfs:label>\n'
                  f'<skos:notation{TYPED}>folio:Test</skos:notation>')
    wp = ontology('<rdfs:label>folio:Test</rdfs:label>')
    diff = compare(tmp_path, gh, wp)
    assert diff.label_normalizations[SUBJECT] == ("Test", "folio:Test")


@pytest.mark.parametrize("gh_attr,wp_attr", [("", TYPED), (TYPED, "")])
def test_has_value_restriction_uses_string_equivalence(tmp_path, gh_attr, wp_attr):
    def restriction(attr):
        return ('<rdfs:subClassOf><owl:Restriction>'
                '<owl:onProperty rdf:resource="https://example.test/property"/>'
                f'<owl:hasValue{attr}>x</owl:hasValue>'
                '</owl:Restriction></rdfs:subClassOf>')
    diff = compare(tmp_path, ontology(restriction(gh_attr)), ontology(restriction(wp_attr)))
    assert not diff.new_restrictions
