#!/usr/bin/env python3
"""Load the local FOLIO RDF/XML file and summarize its declared classes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rdflib import Graph, OWL, RDF, URIRef


DEFAULT_ONTOLOGY = Path(__file__).resolve().parents[1] / "FOLIO.owl"


def local_path(value: str | Path) -> Path:
    """Return *value* as a local path, rejecting URI-shaped inputs."""
    text = str(value)
    if "://" in text or text.startswith(("data:", "file:")):
        raise ValueError("ontology input must be a local filesystem path, not a URL")
    return Path(value)


def load_graph(source: str | Path = DEFAULT_ONTOLOGY) -> Graph:
    """Parse a local RDF/XML ontology without resolving imports or changing it."""
    path = local_path(source)
    data = path.read_bytes()
    graph = Graph()
    graph.parse(data=data, format="xml", publicID=path.resolve().as_uri())
    return graph


def declared_classes(graph: Graph) -> list[str]:
    """Return sorted IRIs explicitly declared as named OWL classes."""
    return sorted(
        str(subject)
        for subject in graph.subjects(RDF.type, OWL.Class)
        if isinstance(subject, URIRef)
    )


def summarize(graph: Graph, sample_limit: int = 10) -> dict[str, object]:
    classes = declared_classes(graph)
    return {
        "triple_count": len(graph),
        "declared_named_class_count": len(classes),
        "class_iri_sample": classes[:sample_limit],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "ontology",
        nargs="?",
        default=DEFAULT_ONTOLOGY,
        help="local RDF/XML ontology (default: repository FOLIO.owl)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = summarize(load_graph(args.ontology))
    except Exception as exc:
        # RDFLib exposes parser failures through several exception subclasses.
        print(f"error: could not load ontology: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
