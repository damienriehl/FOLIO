"""New altLabels and hiddenLabels on existing classes reach the merge output."""

from __future__ import annotations

import sys
from pathlib import Path

import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import SKOS

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from generate_webprotege_merge import apply_changes, compute_semantic_diff

SUBJECT = "https://folio.openlegalstandard.org/Test"


def ontology(*labels: str) -> str:
    body = "".join(f"\n        {label}" for label in labels)
    return f"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:owl="http://www.w3.org/2002/07/owl#"
 xmlns:skos="http://www.w3.org/2004/02/skos/core#">
    <owl:Class rdf:about="{SUBJECT}">
        <skos:prefLabel>Contracts</skos:prefLabel>{body}
    </owl:Class>
</rdf:RDF>
"""


def merge(tmp_path, github: str, webprotege: str) -> tuple[object, str]:
    path = tmp_path / "github.owl"
    path.write_text(github, encoding="utf-8")
    diff = compute_semantic_diff(str(path), webprotege)
    return diff, apply_changes(webprotege, diff, github)


def objects(content: str, predicate) -> set:
    graph = rdflib.Graph().parse(data=content, format="xml")
    return set(graph.objects(URIRef(SUBJECT), predicate))


def test_new_hidden_label_is_detected_and_applied(tmp_path):
    github = ontology("<skos:hiddenLabel>Pact</skos:hiddenLabel>")
    diff, output = merge(tmp_path, github, ontology())
    assert diff.new_hidden_labels == {SUBJECT: [Literal("Pact")]}
    assert not diff.new_alt_labels
    assert objects(output, SKOS.hiddenLabel) == {Literal("Pact")}
    assert not objects(output, SKOS.altLabel)


def test_new_alt_label_is_still_applied_with_language(tmp_path):
    github = ontology('<skos:altLabel xml:lang="fr-fr">Accords</skos:altLabel>')
    diff, output = merge(tmp_path, github, ontology())
    assert diff.new_alt_labels == {SUBJECT: [Literal("Accords", lang="fr-fr")]}
    assert objects(output, SKOS.altLabel) == {Literal("Accords", lang="fr-fr")}


def test_inserted_labels_keep_property_indentation(tmp_path):
    github = ontology("<skos:hiddenLabel>Pact</skos:hiddenLabel>")
    _, output = merge(tmp_path, github, ontology())
    assert "\n        <skos:hiddenLabel>Pact</skos:hiddenLabel>\n    </owl:Class>" in output


def test_merge_is_idempotent(tmp_path):
    github = ontology("<skos:hiddenLabel>Pact</skos:hiddenLabel>")
    _, first = merge(tmp_path, github, ontology())
    diff, second = merge(tmp_path, github, first)
    assert not diff.new_hidden_labels
    assert second == first
