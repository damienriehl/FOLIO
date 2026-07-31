"""Canonical graph fidelity checks for WebProtégé merge artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, URIRef
from rdflib.compare import graph_diff, to_canonical_graph


def _literal(value: dict[str, Any]) -> Literal:
    if value.get("object_kind") != "literal":
        raise ValueError("accepted ledger contains an unsupported object kind")
    if value.get("language") and value.get("datatype"):
        raise ValueError("literal cannot have both language and datatype")
    return Literal(
        value["lexical"],
        lang=value.get("language"),
        datatype=URIRef(value["datatype"]) if value.get("datatype") else None,
    )


def _triple(value: dict[str, Any]) -> tuple[URIRef, URIRef, Literal]:
    return URIRef(value["subject"]), URIRef(value["predicate"]), _literal(value)


def verify_merge_fidelity(
    *,
    webprotege_base_path: str | Path,
    merge_output_path: str | Path,
    manifest: dict[str, Any],
    accepted_states: dict[str, str],
) -> dict[str, Any]:
    """Prove that base-to-output graph changes equal the accepted ledger."""
    records = manifest["payload"]["records"]
    record_ids = {record["record_id"] for record in records}
    if record_ids != set(accepted_states):
        raise ValueError("accepted state IDs do not exactly match manifest")
    rejected = sorted(
        record_id
        for record_id, state in accepted_states.items()
        if state != "accepted"
    )
    if rejected:
        raise ValueError("ledger contains records that are not accepted")
    if manifest["payload"].get("unrelated_semantic_drift"):
        raise ValueError("manifest contains unrelated semantic drift")

    expected_removed = Graph()
    expected_added = Graph()
    for record in records:
        if record.get("before"):
            expected_removed.add(_triple(record["before"]))
        if record.get("after"):
            expected_added.add(_triple(record["after"]))

    base = Graph().parse(str(webprotege_base_path), format="xml")
    output = Graph().parse(str(merge_output_path), format="xml")
    _, actual_removed, actual_added = graph_diff(
        to_canonical_graph(base), to_canonical_graph(output)
    )
    unexpected_removed = set(actual_removed) - set(expected_removed)
    unexpected_added = set(actual_added) - set(expected_added)
    missing_removed = set(expected_removed) - set(actual_removed)
    missing_added = set(expected_added) - set(actual_added)
    if unexpected_removed or unexpected_added:
        raise ValueError("merge output contains unrelated semantic changes")
    if missing_removed:
        raise ValueError("merge output retains stale accepted values")
    if missing_added:
        raise ValueError("merge output is missing accepted values")
    return {
        "verified": True,
        "accepted_record_count": len(records),
        "removed_triple_count": len(actual_removed),
        "added_triple_count": len(actual_added),
    }
