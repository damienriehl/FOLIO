"""Score emitted mappings against an independently judged pair sample."""
from __future__ import annotations

from collections import Counter
import csv
from pathlib import Path

GOLD_COLUMNS = "subject_id object_id verdict expected_predicate note".split()


def read_gold(path: str | Path) -> list[dict]:
    """Read a gold TSV, ignoring its free-text comment header."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader((line for line in handle if not line.startswith("#")), delimiter="\t", quoting=csv.QUOTE_NONE)
        if reader.fieldnames != GOLD_COLUMNS:
            raise ValueError("Gold columns must equal: " + "\t".join(GOLD_COLUMNS))
        gold = list(reader)
    _gold_pairs(gold)
    return gold


def _gold_pairs(gold: list[dict]) -> dict[tuple[str, str], dict]:
    pairs = {}
    for row in gold:
        if row.get("verdict") not in {"correct", "incorrect"}:
            raise ValueError("Gold verdict must be correct or incorrect")
        if any(row.get(key) is None for key in GOLD_COLUMNS) or None in row:
            raise ValueError("Malformed gold record")
        pair = (row["subject_id"], row["object_id"])
        if pair in pairs:
            raise ValueError(f"Duplicate gold pair: {pair}")
        pairs[pair] = row
    return pairs


def score(rows: list[dict], gold: list[dict]) -> dict:
    """Compute precision, recall and judged predicate agreement (four decimals)."""
    pairs = _gold_pairs(gold)
    emitted = {(row["subject_id"], row["object_id"]) for row in rows}
    judged = [row for row in rows if (row["subject_id"], row["object_id"]) in pairs]
    correct = [row for row in judged if pairs[row["subject_id"], row["object_id"]]["verdict"] == "correct"]
    gold_correct = {pair for pair, row in pairs.items() if row["verdict"] == "correct"}
    expected = [row for row in correct if pairs[row["subject_id"], row["object_id"]]["expected_predicate"]]
    agreement = sum(row["predicate_id"] == pairs[row["subject_id"], row["object_id"]]["expected_predicate"] for row in expected)
    def ratio(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None
    return {
        "judged": len(pairs), "emitted_judged": len(judged),
        "precision": ratio(len(correct), len(judged)),
        "recall": ratio(len(emitted & gold_correct), len(gold_correct)),
        "predicate_agreement": ratio(agreement, len(expected)),
        "rows": len(rows),
        "rows_by_predicate": dict(sorted(Counter(row["predicate_id"] for row in rows).items())),
    }
