"""Deterministic stratified legacy-corpus surveillance."""

from __future__ import annotations

import math
import json
from collections import defaultdict
from statistics import NormalDist
from typing import Any
from pathlib import Path
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, SKOS

from .records import canonical_json, content_hash
from .validators import TARGET_PREDICATES

FAMILY = {
    str(SKOS.definition): "definition",
    str(SKOS.example): "example",
}


def surveillance_record_id(value: dict[str, Any]) -> str:
    return content_hash(canonical_json({
        "subject": value["subject"],
        "predicate": value["predicate"],
        "lexical": value["lexical"],
        "locale": (value.get("language") or "en").lower(),
    }))


def build_legacy_records(
    graph: Graph, changed_ids: set[str]
) -> list[dict[str, Any]]:
    """Build the lightweight deterministic surveillance population."""
    records = []
    label_predicates = {
        RDFS.label, SKOS.prefLabel, SKOS.altLabel, SKOS.hiddenLabel,
    }
    for subject, predicate, value in graph:
        if (
            predicate not in TARGET_PREDICATES
            or not isinstance(subject, URIRef)
            or not isinstance(value, Literal)
        ):
            continue
        locale = (value.language or "en").lower()
        family = FAMILY.get(str(predicate))
        if family is None and predicate in label_predicates and locale != "en":
            family = "translation"
        if family is None:
            continue
        record_id = surveillance_record_id({
            "subject": str(subject), "predicate": str(predicate),
            "lexical": str(value), "language": value.language,
        })
        if record_id in changed_ids:
            continue
        records.append({
            "record_id": record_id, "family": family, "locale": locale,
            "risk_tier": "standard", "subject": str(subject),
            "predicate": str(predicate), "annotation": str(value),
            "after": {
                "subject": str(subject), "predicate": str(predicate),
                "object_kind": "literal", "language": value.language,
                "datatype": (
                    str(value.datatype) if value.datatype else None
                ),
                "lexical": str(value),
            },
        })
    return sorted(records, key=lambda item: item["record_id"])


def _stratum(record: dict[str, Any]) -> str:
    return "|".join(
        str(record.get(field) or "unknown")
        for field in ("family", "locale", "risk_tier")
    )


def _sample_size(population: int, *, confidence: float, margin: float) -> int:
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    unbounded = z * z * .25 / (margin * margin)
    finite = unbounded / (1 + ((unbounded - 1) / max(population, 1)))
    return min(population, max(1, math.ceil(finite)))


def select_surveillance_sample(
    records: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    config = policy["surveillance"]
    policy_hash = content_hash(canonical_json(config))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ids = set()
    for record in records:
        record_id = record["record_id"]
        if record_id in ids:
            raise ValueError(f"duplicate surveillance record ID: {record_id}")
        ids.add(record_id)
        grouped[_stratum(record)].append(record)
    population_hash = content_hash(canonical_json(sorted(ids)))
    strata = {}
    total = 0
    simultaneous_confidence = 1 - (
        (1 - float(config["confidence"])) / max(len(grouped), 1)
    )
    for name, items in sorted(grouped.items()):
        ordered = sorted(
            items,
            key=lambda item: content_hash(
                canonical_json(
                    {
                        "seed": config["seed"],
                        "policy_hash": policy_hash,
                        "population_hash": population_hash,
                        "record_id": item["record_id"],
                    }
                )
            ),
        )
        census = len(items) <= int(config["rare_stratum_census_at"])
        count = len(items) if census else _sample_size(
            len(items), confidence=simultaneous_confidence, margin=float(config["margin"])
        )
        selected = [item["record_id"] for item in ordered[:count]]
        total += len(selected)
        strata[name] = {
            "population_count": len(items), "sample_count": len(selected),
            "census": census or len(selected) == len(items), "selected_ids": selected,
        }
    if total > int(config["maximum_review_records"]):
        raise ValueError("surveillance sample exceeds configured review budget")
    return {
        "policy_hash": policy_hash, "population_hash": population_hash,
        "seed": config["seed"], "strata": strata, "selected_count": total,
    }


def _wilson_upper(defects: int, sample: int, confidence: float) -> float:
    if sample == 0:
        return 1.0
    z = NormalDist().inv_cdf(confidence)
    proportion = defects / sample
    denominator = 1 + z * z / sample
    center = proportion + z * z / (2 * sample)
    spread = z * math.sqrt(proportion * (1 - proportion) / sample + z * z / (4 * sample * sample))
    return min(1.0, (center + spread) / denominator)


def evaluate_surveillance(
    sample: dict[str, Any],
    records: list[dict[str, Any]],
    results: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    if sample["policy_hash"] != content_hash(canonical_json(policy["surveillance"])):
        raise ValueError("surveillance policy changed after sampling")
    current_ids = sorted(record["record_id"] for record in records)
    if sample["population_hash"] != content_hash(canonical_json(current_ids)):
        raise ValueError("surveillance population changed after sampling")
    by_stratum: dict[str, list[str]] = defaultdict(list)
    for record in records:
        by_stratum[_stratum(record)].append(record["record_id"])
    severe_classes = set(policy["surveillance"]["severe_defect_classes"])
    summaries = {}
    debt = []
    blocked = False
    simultaneous_confidence = 1 - (
        (1 - float(policy["surveillance"]["confidence"]))
        / max(len(sample["strata"]), 1)
    )
    for name, selection in sample["strata"].items():
        selected = selection["selected_ids"]
        missing = sorted(set(selected) - set(results))
        defects = [
            record_id for record_id in selected
            if results.get(record_id, {}).get("verdict") == "defect"
        ]
        severe = [
            record_id for record_id in defects
            if severe_classes & set(results[record_id].get("defect_types", []))
        ]
        upper = _wilson_upper(
            len(defects), len(selected), simultaneous_confidence
        )
        requires_census = bool(severe) or upper > float(policy["surveillance"]["maximum_defect_rate"])
        expansion = sorted(set(by_stratum[name]) - set(selected)) if requires_census else []
        if missing or expansion:
            blocked = True
        for record_id in defects:
            debt.append({
                "record_id": record_id,
                "defect_types": sorted(results[record_id].get("defect_types", [])),
                "discovery": "legacy-surveillance",
                "state": "open",
            })
        summaries[name] = {
            "missing_ids": missing, "defect_count": len(defects),
            "severe_defect_ids": severe, "simultaneous_upper_bound": upper,
            "requires_census": requires_census, "expansion_ids": expansion,
        }
    return {
        "decision": "blocked" if blocked else "pass",
        "strata": summaries,
        "debt": sorted(debt, key=lambda item: item["record_id"]),
    }


def append_debt_ledger(path: str | Path, entries: list[dict[str, Any]]) -> None:
    destination = Path(path)
    existing = []
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
    by_id = {item["record_id"]: item for item in existing}
    for entry in entries:
        prior = by_id.get(entry["record_id"])
        if prior and prior != entry:
            raise ValueError(f"append-only debt entry changed: {entry['record_id']}")
        by_id[entry["record_id"]] = entry
    data = canonical_json(sorted(by_id.values(), key=lambda item: item["record_id"])) + b"\n"
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(data)
    temporary.replace(destination)
