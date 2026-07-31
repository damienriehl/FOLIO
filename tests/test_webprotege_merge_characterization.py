"""Characterization coverage for the existing merge utility before reuse."""

from __future__ import annotations

import sys
from pathlib import Path

from rdflib.namespace import SKOS

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from generate_webprotege_merge import compute_semantic_diff

SUBJECT = "https://folio.openlegalstandard.org/Test"


def ontology(definition: str) -> str:
    return f"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:owl="http://www.w3.org/2002/07/owl#"
 xmlns:skos="http://www.w3.org/2004/02/skos/core#">
<owl:Class rdf:about="{SUBJECT}">
  <skos:definition xml:lang="en">{definition}</skos:definition>
</owl:Class>
</rdf:RDF>"""


def test_identical_graph_has_no_content_changes(tmp_path):
    path = tmp_path / "candidate.owl"
    path.write_text(ontology("Definition"), encoding="utf-8")
    diff = compute_semantic_diff(str(path), ontology("Definition"))
    assert not diff.new_classes
    assert not diff.definition_updates
    assert not diff.removals


def test_one_to_one_definition_change_is_detected(tmp_path):
    path = tmp_path / "candidate.owl"
    path.write_text(ontology("Corrected"), encoding="utf-8")
    diff = compute_semantic_diff(str(path), ontology("Old"))
    assert [str(value) for value in diff.definition_updates[SUBJECT]] == ["Corrected"]
