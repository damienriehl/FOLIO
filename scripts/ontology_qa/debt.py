"""Confirmed legacy-debt validation and atomic lifecycle receipts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, URIRef

from .records import AnnotationValue, canonical_json, content_hash


def debt_root_id(entry: dict[str, Any]) -> str:
    return content_hash(canonical_json({
        "debt_id": entry["debt_id"], "subject": entry["subject"],
        "predicate": entry["predicate"], "language": entry["language"],
        "datatype": entry["datatype"], "current_hash": entry["current_hash"],
    }))


def load_debt(path: str | Path) -> list[dict[str, Any]]:
    entries = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [entry["debt_id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate debt ID")
    locators = [
        (entry["subject"], entry["predicate"], entry["language"], entry["datatype"], entry["current_hash"])
        for entry in entries
    ]
    if len(locators) != len(set(locators)):
        raise ValueError("duplicate debt locator")
    if any("replacement" in entry for entry in entries):
        raise ValueError("debt discovery ledger cannot contain proposed replacement text")
    if any(entry.get("state") != "open" for entry in entries):
        raise ValueError("confirmed-defect source ledger must remain open and append-only")
    return entries


def validate_debt_targets(
    ontology_path: str | Path, entries: list[dict[str, Any]]
) -> dict[str, str]:
    graph = Graph().parse(ontology_path, format="xml")
    matched = {}
    for entry in entries:
        values = [
            obj for obj in graph.objects(URIRef(entry["subject"]), URIRef(entry["predicate"]))
            if isinstance(obj, Literal)
            and (obj.language.lower() if obj.language else None) == entry["language"]
            and (str(obj.datatype) if obj.datatype else None) == entry["datatype"]
        ]
        matching_hashes = [
            AnnotationValue(
                entry["subject"], entry["predicate"], str(value),
                language=value.language,
                datatype=str(value.datatype) if value.datatype else None,
            ).value_hash
            for value in values
        ]
        if matching_hashes.count(entry["current_hash"]) != 1:
            raise ValueError(f"stale, missing, or ambiguous debt target: {entry['debt_id']}")
        matched[entry["debt_id"]] = entry["current_hash"]
    return matched


def publish_migration_receipt(
    destination: str | Path,
    *,
    entries: list[dict[str, Any]],
    correction_ledger: list[dict[str, Any]],
    release_report: dict[str, Any],
    final_ontology_path: str | Path,
) -> dict[str, Any]:
    if release_report["payload"].get("release_decision") != "merge_gate_passed":
        raise ValueError("debt migration cannot close without a passing release report")
    roots = {item["root_record_id"] for item in correction_ledger}
    missing = sorted(entry["debt_id"] for entry in entries if debt_root_id(entry) not in roots)
    if missing:
        raise ValueError(f"debt migration has incomplete correction lineage: {missing}")
    receipt_body = {
        "source_debt_hash": content_hash(canonical_json(entries)),
        "closed_debt_ids": sorted(entry["debt_id"] for entry in entries),
        "correction_revision_ids": sorted(item["revision_id"] for item in correction_ledger),
        "release_report_hash": release_report["artifact_hash"],
        "final_ontology_hash": content_hash(Path(final_ontology_path).read_bytes()),
    }
    receipt = {"receipt_hash": content_hash(canonical_json(receipt_body)), **receipt_body}
    target = Path(destination)
    if target.exists():
        raise FileExistsError("migration receipt is append-only")
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(canonical_json(receipt) + b"\n")
    temporary.replace(target)
    return receipt
