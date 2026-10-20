"""Bounded, content-addressed ontology review context."""

from __future__ import annotations

from typing import Any

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, SKOS

from .records import canonical_json, content_hash


def build_context(
    record: dict[str, Any],
    *,
    concept_label: str,
    source_annotation: dict[str, Any] | None,
    concept_definition: dict[str, Any] | None,
    ancestors: list[str],
    siblings: list[str],
    risk_evidence: list[dict[str, Any]],
    maximum_items: int = 12,
    maximum_chars: int = 8000,
) -> dict[str, Any]:
    context = {
        "record": {
            key: value for key, value in record.items() if key != "context"
        },
        "concept_label": concept_label,
        "source_annotation": source_annotation,
        "concept_definition": concept_definition,
        "ancestors": sorted(set(ancestors))[:maximum_items],
        "siblings": sorted(set(siblings))[:maximum_items],
        "risk_evidence": risk_evidence[:maximum_items],
    }
    encoded = canonical_json(context)
    if len(encoded) > maximum_chars:
        context["ancestors"] = context["ancestors"][:3]
        context["siblings"] = context["siblings"][:3]
        context["risk_evidence"] = context["risk_evidence"][:3]
        encoded = canonical_json(context)
    if len(encoded) > maximum_chars:
        raise ValueError("review context exceeds configured bound")
    return {"context_hash": content_hash(encoded), **context}


def build_graph_context(
    graph: Graph,
    record: dict[str, Any],
    *,
    risk_evidence: list[dict[str, Any]],
    maximum_items: int = 12,
    maximum_chars: int = 8000,
) -> dict[str, Any]:
    """Derive compact ontology context for one immutable delta record."""
    value = record.get("after") or record.get("before")
    if not value:
        raise ValueError("delta record has neither before nor after value")
    subject = URIRef(value["subject"])

    def labels(node: URIRef) -> list[str]:
        candidates: list[tuple[int, str]] = []
        for priority, predicate in enumerate(
            (SKOS.prefLabel, RDFS.label, SKOS.altLabel)
        ):
            for literal in graph.objects(node, predicate):
                if isinstance(literal, Literal):
                    language = (literal.language or "").lower()
                    language_priority = 0 if language in {"en", "en-us", ""} else 1
                    candidates.append(
                        (priority * 2 + language_priority, str(literal))
                    )
        return [
            text for _, text in sorted(set(candidates), key=lambda item: item)
        ]

    ancestor_nodes = sorted(
        {
            parent
            for parent in graph.objects(subject, RDFS.subClassOf)
            if isinstance(parent, URIRef)
        },
        key=str,
    )
    sibling_nodes = sorted(
        {
            sibling
            for parent in ancestor_nodes
            for sibling in graph.subjects(RDFS.subClassOf, parent)
            if isinstance(sibling, URIRef) and sibling != subject
        },
        key=str,
    )
    concept_labels = labels(subject)
    target_literal = value.get("lexical")

    def annotation_values(predicate: URIRef) -> list[dict[str, Any]]:
        return sorted(
            [
                {
                    "predicate": str(predicate),
                    "language": literal.language,
                    "lexical": str(literal),
                }
                for literal in graph.objects(subject, predicate)
                if isinstance(literal, Literal)
            ],
            key=lambda item: (
                0 if (item["language"] or "").lower() in {"en", ""} else 1,
                item["language"] or "",
                item["lexical"],
            ),
        )

    source_candidates = [
        item
        for item in annotation_values(URIRef(value["predicate"]))
        if item["lexical"] != target_literal
        and (item["language"] or "").lower() in {"en", ""}
    ]
    definitions = [
        item for item in annotation_values(SKOS.definition)
        if (item["language"] or "").lower() in {"en", "en-us", ""}
    ]
    ancestors = [
        label
        for node in ancestor_nodes
        for label in labels(node)[:1]
    ]
    siblings = [
        label
        for node in sibling_nodes
        for label in labels(node)[:1]
    ]
    relevant_risks = [
        finding
        for finding in risk_evidence
        if finding.get("subject") == str(subject)
        and (
            not finding.get("predicate")
            or finding.get("predicate") == value["predicate"]
        )
    ]
    return build_context(
        record,
        concept_label=concept_labels[0] if concept_labels else str(subject),
        source_annotation=(
            source_candidates[0] if len(source_candidates) == 1 else None
        ),
        concept_definition=definitions[0] if definitions else None,
        ancestors=ancestors,
        siblings=siblings,
        risk_evidence=relevant_risks,
        maximum_items=maximum_items,
        maximum_chars=maximum_chars,
    )
