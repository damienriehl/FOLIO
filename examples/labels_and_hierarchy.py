#!/usr/bin/env python3
"""Inspect labels and asserted direct hierarchy for one declared FOLIO class."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rdflib import BNode, Graph, Literal, OWL, RDF, RDFS, SKOS, URIRef

from load_and_inspect import DEFAULT_ONTOLOGY, load_graph


LABEL_PREDICATES = (RDFS.label, SKOS.prefLabel, SKOS.altLabel, SKOS.hiddenLabel)


def term_record(term: object) -> dict[str, object]:
    if isinstance(term, Literal):
        return {
            "term_kind": "literal",
            "value": str(term),
            "language": term.language,
            "datatype": str(term.datatype) if term.datatype else None,
        }
    if isinstance(term, URIRef):
        return {"term_kind": "iri", "value": str(term)}
    if isinstance(term, BNode):
        return {"term_kind": "blank_node", "value": str(term)}
    return {"term_kind": type(term).__name__, "value": str(term)}


def deprecation_values(graph: Graph, subject: URIRef) -> list[dict[str, object]]:
    return sorted(
        (term_record(value) for value in graph.objects(subject, OWL.deprecated)),
        key=lambda item: json.dumps(item, sort_keys=True),
    )


def neighbor_record(graph: Graph, iri: URIRef) -> dict[str, object]:
    return {"iri": str(iri), "deprecated": deprecation_values(graph, iri)}


def inspect_class(graph: Graph, iri_text: str) -> dict[str, object]:
    if not iri_text or "://" not in iri_text:
        raise ValueError("concept must be an absolute class IRI")
    subject = URIRef(iri_text)
    if (subject, RDF.type, OWL.Class) not in graph:
        raise ValueError(f"not an explicitly declared named OWL class: {iri_text}")

    labels = []
    for predicate in LABEL_PREDICATES:
        for value in graph.objects(subject, predicate):
            labels.append({"predicate": str(predicate), **term_record(value)})
    labels.sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))

    parents = sorted(
        {parent for parent in graph.objects(subject, RDFS.subClassOf) if isinstance(parent, URIRef)},
        key=str,
    )
    children = sorted(
        {child for child in graph.subjects(RDFS.subClassOf, subject) if isinstance(child, URIRef)},
        key=str,
    )
    return {
        "iri": iri_text,
        "labels": labels,
        "deprecated": deprecation_values(graph, subject),
        "direct_parents": [neighbor_record(graph, value) for value in parents],
        "direct_children": [neighbor_record(graph, value) for value in children],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iri", help="full IRI of an explicitly declared OWL class")
    parser.add_argument("--ontology", default=DEFAULT_ONTOLOGY, help="local RDF/XML ontology")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = inspect_class(load_graph(args.ontology), args.iri)
    except Exception as exc:
        print(f"error: could not inspect class: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
