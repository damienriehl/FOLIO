from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.sampling import append_debt_ledger, evaluate_surveillance, select_surveillance_sample

ROOT = Path(__file__).parents[1]
POLICY = yaml.safe_load((ROOT / "qa/ontology/review-policy.yaml").read_text())


def records(count, *, locale="en", family="definition", risk="normal"):
    return [
        {"record_id": f"{index:064x}", "locale": locale, "family": family, "risk_tier": risk}
        for index in range(count)
    ]


def passing(sample):
    return {
        record_id: {"verdict": "pass", "defect_types": []}
        for stratum in sample["strata"].values()
        for record_id in stratum["selected_ids"]
    }


def test_rare_locale_is_always_a_census():
    sample = select_surveillance_sample(records(7, locale="he-il"), POLICY)
    stratum = sample["strata"]["definition|he-il|normal"]
    assert stratum["census"] is True
    assert stratum["sample_count"] == 7


def test_selection_is_order_independent_and_retry_stable():
    population = records(500)
    first = select_surveillance_sample(population, POLICY)
    second = select_surveillance_sample(list(reversed(population)), POLICY)
    assert first == second


def test_population_or_policy_change_invalidates_sample():
    population = records(100)
    sample = select_surveillance_sample(population, POLICY)
    with pytest.raises(ValueError, match="population changed"):
        evaluate_surveillance(sample, population[:-1], passing(sample), POLICY)
    changed = deepcopy(POLICY)
    changed["surveillance"]["seed"] = "new-seed"
    with pytest.raises(ValueError, match="policy changed"):
        evaluate_surveillance(sample, population, passing(sample), changed)


def test_severe_defect_expands_deterministically_to_census():
    population = records(500)
    sample = select_surveillance_sample(population, POLICY)
    results = passing(sample)
    record_id = next(iter(results))
    results[record_id] = {"verdict": "defect", "defect_types": ["negation"]}
    first = evaluate_surveillance(sample, population, results, POLICY)
    second = evaluate_surveillance(sample, list(reversed(population)), results, POLICY)
    name = "definition|en|normal"
    assert first == second
    assert first["decision"] == "blocked"
    assert len(first["strata"][name]["expansion_ids"]) + sample["strata"][name]["sample_count"] == 500
    assert first["debt"][0]["record_id"] == record_id


def test_missing_result_or_budget_exhaustion_cannot_pass():
    population = records(100)
    sample = select_surveillance_sample(population, POLICY)
    results = passing(sample)
    results.pop(next(iter(results)))
    assert evaluate_surveillance(sample, population, results, POLICY)["decision"] == "blocked"
    changed = deepcopy(POLICY)
    changed["surveillance"]["maximum_review_records"] = 1
    with pytest.raises(ValueError, match="budget"):
        select_surveillance_sample(population, changed)


def test_debt_ledger_is_append_only(tmp_path):
    path = tmp_path / "debt.json"
    entry = {"record_id": "a" * 64, "defect_types": ["negation"], "discovery": "legacy-surveillance", "state": "open"}
    append_debt_ledger(path, [entry])
    append_debt_ledger(path, [entry])
    changed = {**entry, "state": "closed"}
    with pytest.raises(ValueError, match="append-only"):
        append_debt_ledger(path, [changed])
