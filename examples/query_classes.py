#!/usr/bin/env python3
"""Run a bounded, read-only query over explicitly declared FOLIO classes."""

from __future__ import annotations

import argparse
import json
import sys

from rdflib import Graph, URIRef

from labels_and_hierarchy import term_record
from load_and_inspect import DEFAULT_ONTOLOGY, load_graph


CLASS_QUERY = """
SELECT ?class ?label ?deprecated WHERE {
  ?class a <http://www.w3.org/2002/07/owl#Class> .
  FILTER(isIRI(?class))
  OPTIONAL { ?class <http://www.w3.org/2000/01/rdf-schema#label> ?label . }
  OPTIONAL { ?class <http://www.w3.org/2002/07/owl#deprecated> ?deprecated . }
  FILTER(!BOUND(?parent) || EXISTS {
    ?class <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?parent .
  })
}
ORDER BY STR(?class) COALESCE(STR(?label), "") COALESCE(STR(?deprecated), "")
LIMIT 20
"""


def query_classes(graph: Graph, parent_iri: str | None = None) -> list[dict[str, object]]:
    """Run the fixed query with an optional safely bound direct-parent IRI."""
    bindings = {"parent": URIRef(parent_iri)} if parent_iri else {}
    rows = graph.query(CLASS_QUERY, initBindings=bindings)
    return [
        {
            "iri": str(row["class"]),
            "label": term_record(row["label"]) if row["label"] is not None else None,
            "deprecated": term_record(row["deprecated"]) if row["deprecated"] is not None else None,
        }
        for row in rows
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ontology", default=DEFAULT_ONTOLOGY, help="local RDF/XML ontology")
    parser.add_argument("--parent", help="return only asserted direct children of this full IRI")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows = query_classes(load_graph(args.ontology), args.parent)
    except Exception as exc:
        print(f"error: could not query classes: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"row_count": len(rows), "rows": rows}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
