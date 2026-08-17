"""Coverage for applying definition updates to a WebProtégé export.

`compute_semantic_diff` detecting a definition change is not the same as
`apply_changes` writing it. Those two drifted apart: the apply regex matched a
bare `<skos:definition>` while WebProtégé writes `rdf:datatype="...#string"` and
`xml:lang="..."` on some definitions, so those updates were detected, never
written, and still counted in the summary as applied. `R5RoVVyRmkyMepjXK7X1sp`
(No-Fault Claim) sat diverged that way.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from generate_webprotege_merge import (  # noqa: E402
    apply_changes,
    compute_semantic_diff,
)

SUBJECT = "https://folio.openlegalstandard.org/Test"
OTHER = "https://folio.openlegalstandard.org/Other"

HEADER = (
    '<?xml version="1.0"?>\n'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"\n'
    ' xmlns:owl="http://www.w3.org/2002/07/owl#"\n'
    ' xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"\n'
    ' xmlns:skos="http://www.w3.org/2004/02/skos/core#">\n'
)


def document(*class_bodies: str) -> str:
    return HEADER + "\n".join(class_bodies) + "\n</rdf:RDF>"


def klass(iri: str, definition_tag: str) -> str:
    return f'<owl:Class rdf:about="{iri}">\n  {definition_tag}\n</owl:Class>'


def run(tmp_path: Path, github: str, webprotege: str) -> tuple[str, object]:
    path = tmp_path / "candidate.owl"
    path.write_text(github, encoding="utf-8")
    diff = compute_semantic_diff(str(path), webprotege)
    return apply_changes(webprotege, diff, github), diff


@pytest.mark.parametrize(
    "opening",
    [
        "<skos:definition>",
        '<skos:definition rdf:datatype="http://www.w3.org/2001/XMLSchema#string">',
        '<skos:definition xml:lang="en">',
    ],
)
def test_definition_update_is_applied_whatever_the_attributes(
    tmp_path: Path, opening: str
) -> None:
    """The regression: attributed opening tags were silently skipped."""
    gh = document(klass(SUBJECT, f"{opening}Corrected</skos:definition>"))
    wp = document(klass(SUBJECT, f"{opening}Stale</skos:definition>"))
    result, diff = run(tmp_path, gh, wp)
    assert "Corrected" in result
    assert "Stale" not in result
    assert SUBJECT in diff.definitions_applied


def test_attributes_survive_the_update(tmp_path: Path) -> None:
    """A datatype or language tag must not be dropped by the rewrite."""
    opening = '<skos:definition rdf:datatype="http://www.w3.org/2001/XMLSchema#string">'
    gh = document(klass(SUBJECT, f"{opening}Corrected</skos:definition>"))
    wp = document(klass(SUBJECT, f"{opening}Stale</skos:definition>"))
    result, _ = run(tmp_path, gh, wp)
    assert f"{opening}Corrected</skos:definition>" in result


def test_self_closing_resource_definition_does_not_consume_a_sibling(
    tmp_path: Path,
) -> None:
    """The shape the ontology actually contains.

    <skos:definition rdf:resource="..."/> has no closing tag, so a tolerant
    `.*?</skos:definition>` treats it as an opening tag and runs forward to the
    next closing tag it finds — consuming the resource-valued definition *and*
    the literal one after it, replacing both with a single string.

    In FOLIO-webprotege-merge-output.owl the first of the four such tags is
    immediately followed by a literal definition in the same block, so a naive
    match spans 170 characters and destroys both. That is the real failure
    mode; the following test covers the worse case where the nearest closing
    tag lies in a later class.
    """
    resource_tag = '<skos:definition rdf:resource="https://example.test/video"/>'
    sibling = "<skos:definition>Sibling definition</skos:definition>"
    gh = document(klass(SUBJECT, f"{resource_tag}\n  {sibling}"))
    wp = document(klass(SUBJECT, f"{resource_tag}\n  {sibling}"))
    result, _ = run(tmp_path, gh, wp)
    assert resource_tag in result
    assert sibling in result


def test_self_closing_resource_definition_does_not_swallow_later_classes(
    tmp_path: Path,
) -> None:
    """The worse case: nearest closing tag in a later class.

    Not the shape present in the current file, but nothing prevents it — a
    resource-valued definition whose block has no literal definition after it
    puts the next match a whole class away.
    """
    resource_tag = '<skos:definition rdf:resource="https://example.test/video"/>'
    gh = document(
        klass(SUBJECT, "<skos:definition>Corrected</skos:definition>"),
        klass(OTHER, "<skos:definition>Untouched</skos:definition>"),
    )
    wp = document(
        klass(SUBJECT, resource_tag),
        klass(OTHER, "<skos:definition>Untouched</skos:definition>"),
    )
    result, diff = run(tmp_path, gh, wp)
    # The neighbouring class must survive intact.
    assert "Untouched" in result
    assert f'<owl:Class rdf:about="{OTHER}">' in result
    assert resource_tag in result
    # And the un-appliable update must be reported, not silently counted.
    if SUBJECT in diff.definition_updates:
        assert SUBJECT not in diff.definitions_applied


def test_added_definition_is_appended_not_substituted(tmp_path: Path) -> None:
    """The data-loss regression.

    When FOLIO.owl gains a second definition, the existing one must survive.
    Routing additions through the replacement path overwrote it: the class came
    out with one definition, the wrong one, and nothing said so.
    """
    original = "<skos:definition>Original</skos:definition>"
    added = "<skos:definition>Added second</skos:definition>"
    gh = document(klass(SUBJECT, f"{original}\n  {added}"))
    wp = document(klass(SUBJECT, original))
    result, diff = run(tmp_path, gh, wp)

    assert "Original" in result, "the pre-existing definition was destroyed"
    assert "Added second" in result
    assert result.count("<skos:definition") == 2
    assert SUBJECT in diff.definition_additions
    assert SUBJECT in diff.definitions_added
    # An addition is not a replacement and must not be recorded as one.
    assert SUBJECT not in diff.definition_updates


def test_addition_preserves_language_and_datatype(tmp_path: Path) -> None:
    """A language tag or datatype is part of the literal's identity."""
    original = "<skos:definition>Original</skos:definition>"
    tagged = '<skos:definition xml:lang="fr-fr">Definition francaise</skos:definition>'
    gh = document(klass(SUBJECT, f"{original}\n  {tagged}"))
    wp = document(klass(SUBJECT, original))
    result, _ = run(tmp_path, gh, wp)
    assert tagged in result
    assert "Original" in result


def test_addition_is_not_duplicated_when_already_present(tmp_path: Path) -> None:
    original = "<skos:definition>Original</skos:definition>"
    gh = document(klass(SUBJECT, original))
    wp = document(klass(SUBJECT, original))
    result, diff = run(tmp_path, gh, wp)
    assert not diff.definition_additions
    assert result.count("<skos:definition") == 1


def test_replacement_still_substitutes(tmp_path: Path) -> None:
    """The 1:1 path must keep replacing, not start appending."""
    gh = document(klass(SUBJECT, "<skos:definition>Corrected</skos:definition>"))
    wp = document(klass(SUBJECT, "<skos:definition>Stale</skos:definition>"))
    result, diff = run(tmp_path, gh, wp)
    assert result.count("<skos:definition") == 1
    assert "Corrected" in result and "Stale" not in result
    assert SUBJECT in diff.definition_updates
    assert SUBJECT not in diff.definition_additions


def test_added_definition_on_a_class_with_none(tmp_path: Path) -> None:
    """A class with no definition at all still receives one."""
    gh = document(klass(SUBJECT, "<skos:definition>First</skos:definition>"))
    wp = document(klass(SUBJECT, "<rdfs:label>Test</rdfs:label>"))
    result, diff = run(tmp_path, gh, wp)
    assert "First" in result
    assert "<rdfs:label>Test</rdfs:label>" in result
    assert SUBJECT in diff.definitions_added


def test_definitions_applied_starts_empty_and_tracks_only_writes(
    tmp_path: Path,
) -> None:
    gh = document(klass(SUBJECT, "<skos:definition>Same</skos:definition>"))
    wp = document(klass(SUBJECT, "<skos:definition>Same</skos:definition>"))
    result, diff = run(tmp_path, gh, wp)
    assert diff.definitions_applied == set()
    assert result == wp
