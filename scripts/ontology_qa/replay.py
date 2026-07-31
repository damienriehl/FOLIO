"""Offline verification of ontology QA evidence bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml
from rdflib import Graph

from .evals import (
    corpus_identity, evaluate_predictions, load_cases,
    load_slice_controls,
)
from .correction_evidence import verify_correction_lineage
from .reconcile import reconcile
from .records import canonical_json, content_hash
from .reporting import validate_artifact_hash, validate_qualification_hash
from .sampling import (
    build_legacy_records, evaluate_surveillance,
    select_surveillance_sample, surveillance_record_id,
)


def _read_json(path: Path, *, canonical: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable artifact {path.name}: {exc}") from exc
    if canonical and raw != canonical_json(value) + b"\n":
        raise ValueError(f"artifact bytes are not canonical: {path.name}")
    return value


def replay_bundle(bundle_path: str | Path, *, report_schema_path: str | Path) -> dict[str, Any]:
    root = Path(bundle_path)
    index = _read_json(root / "index.json", canonical=True)
    report = _read_json(root / "report.json", canonical=True)
    validate_artifact_hash(report)
    Draft202012Validator(
        _read_json(Path(report_schema_path))
    ).validate(report)
    if report["artifact_hash"] != index.get("report_hash"):
        raise ValueError("bundle index report hash mismatch")
    if report["candidate_hash"] != index.get("candidate_hash"):
        raise ValueError("bundle index candidate hash mismatch")
    actual_files = sorted(path.name for path in root.iterdir() if not path.name.startswith(".") and path.name != "index.json")
    indexed_files = sorted(name for name in index.get("files", []) if name != "index.json")
    if actual_files != indexed_files:
        raise ValueError("bundle file set is incomplete or contains unindexed evidence")
    artifacts = {}
    for stage, expected_hash in report["payload"]["stage_hashes"].items():
        artifact = _read_json(root / f"{stage}.json", canonical=True)
        if stage.endswith("_qualification"):
            validate_qualification_hash(artifact)
            if artifact["qualification_hash"] != expected_hash:
                raise ValueError(f"qualification hash mismatch: {stage}")
        else:
            validate_artifact_hash(artifact)
            if artifact["artifact_hash"] != expected_hash:
                raise ValueError(f"stage hash mismatch: {stage}")
            if artifact["candidate_hash"] != report["candidate_hash"]:
                raise ValueError(f"stale candidate binding: {stage}")
        artifacts[stage] = artifact
    if content_hash((root / "candidate.owl").read_bytes()) != report["candidate_hash"]:
        raise ValueError("candidate ontology bytes do not match report")
    if content_hash((root / "baseline.owl").read_bytes()) != report["baseline_hash"]:
        raise ValueError("baseline ontology bytes do not match report")
    parent_hashes = set(report["parent_hashes"])
    if parent_hashes != set(report["payload"]["stage_hashes"].values()):
        raise ValueError("report parent graph is incomplete")
    manifest_ids = {
        item["record_id"] for item in artifacts["manifest"]["payload"]["records"]
    }
    if manifest_ids != set(report["payload"]["record_states"]):
        raise ValueError("final delta and record-state sets differ")
    if (
        artifacts["primary"]["payload"].get("qualification_hash")
        != artifacts["primary_qualification"]["qualification_hash"]
        or artifacts["independent"]["payload"].get("qualification_hash")
        != artifacts["independent_qualification"]["qualification_hash"]
    ):
        raise ValueError("assessment and qualification bindings differ")
    primary_q = artifacts["primary_qualification"]
    independent_q = artifacts["independent_qualification"]
    if primary_q.get("status") != "qualified" or independent_q.get("status") != "qualified":
        raise ValueError("release uses an unqualified model route")
    if (
        artifacts["primary"].get("status") != "complete"
        or artifacts["independent"].get("status") != "complete"
    ):
        raise ValueError("release uses incomplete model assessments")
    for assessment, qualification in (
        (artifacts["primary"], primary_q),
        (artifacts["independent"], independent_q),
    ):
        if (
            assessment["payload"].get("provider") != qualification["provider"]
            or assessment["payload"].get("model") != qualification["requested_model"]
            or assessment["payload"].get("actual_model") != qualification["actual_model"]
        ):
            raise ValueError("assessment route differs from qualification")

    model_policy_path = root / "model-policy.yaml"
    if model_policy_path.exists():
        review_policy_path = root / "review-policy.yaml"
        expected_policy_hash = content_hash(
            model_policy_path.read_bytes() + review_policy_path.read_bytes()
        )
        if expected_policy_hash != report["policy_hash"]:
            raise ValueError("snapshotted policy hash mismatch")
        model_policy = yaml.safe_load(model_policy_path.read_text(encoding="utf-8"))
        minimum_confidence = float(model_policy["minimum_confidence"])
        schema = _read_json(root / "review-schema.json")
        schema_hash = content_hash(canonical_json(schema))
        prompt_hash = content_hash(canonical_json({
            family: (root / name).read_text(encoding="utf-8")
            for family, name in (
                ("definition", "prompt-definition.md"),
                ("example", "prompt-example.md"),
                ("translation", "prompt-translation.md"),
                ("correction-proposal", "prompt-correction-proposal.md"),
                ("correction-verification", "prompt-correction-verification.md"),
            )
        }))
        corpus_hash = corpus_identity(
            [
                root / "eval-cases.jsonl",
                root / "eval-held-out.jsonl",
                root / "eval-slice-controls.json",
            ]
        )
        for qualification in (primary_q, independent_q):
            if (
                qualification["schema_hash"] != schema_hash
                or qualification["prompt_hash"] != prompt_hash
                or qualification["corpus_hash"] != corpus_hash
                or qualification["policy_hash"] != report["policy_hash"]
            ):
                raise ValueError("qualification inputs differ from snapshots")
        required_slices = {
            (family, locale)
            for family, locales in model_policy[
                "required_slices"
            ].items()
            for locale in locales
        }
        evaluation_cases = [
            case
            for path in (
                root / "eval-cases.jsonl",
                root / "eval-held-out.jsonl",
            )
            for case in load_cases(path)
        ] + load_slice_controls(
            root / "eval-slice-controls.json", required_slices
        )
        id_map = {
            content_hash(case["case_id"]): case["case_id"]
            for case in evaluation_cases
        }
        for qualification in (primary_q, independent_q):
            rounds = qualification["metrics"].get(
                "evaluation_rounds"
            )
            if not isinstance(rounds, list) or len(rounds) != 2:
                raise ValueError(
                    "qualification lacks replayable evaluation rounds"
                )
            predictions_by_round = []
            for responses in rounds:
                if (
                    {item.get("record_id") for item in responses}
                    != set(id_map)
                    or len(responses) != len(id_map)
                ):
                    raise ValueError(
                        "qualification evaluation response set differs"
                    )
                for response in responses:
                    Draft202012Validator(schema).validate(response)
                predictions_by_round.append({
                    id_map[item["record_id"]]: item["verdict"]
                    for item in responses
                })
            recomputed = evaluate_predictions(
                evaluation_cases, predictions_by_round[0],
                minimum_cases_per_slice=int(
                    model_policy["minimum_scored_cases_per_slice"]
                ),
                required_slices=required_slices,
            )
            recomputed["repeat_stability"] = (
                predictions_by_round[0] == predictions_by_round[1]
            )
            for field in (
                "scored_count", "challenge_count",
                "missing_case_ids", "accuracy", "defect_recall",
                "false_accept_rate", "unsupported_slices",
                "slice_metrics", "repeat_stability",
            ):
                if qualification["metrics"].get(field) != recomputed[field]:
                    raise ValueError(
                        f"qualification metric differs on replay: {field}"
                    )
        tool_manifest = _read_json(root / "tool-manifest.json", canonical=True)
        claimed_tool_hash = tool_manifest.pop("tool_hash", None)
        if (
            content_hash(canonical_json(tool_manifest)) != claimed_tool_hash
            or claimed_tool_hash != report["tool_hash"]
        ):
            raise ValueError("tool manifest hash mismatch")
    else:
        minimum_confidence = 0.9

    correction_lineage = report["payload"].get("correction_lineage")
    if correction_lineage is not None:
        expected_routes = None
        expected_prompt_hash = None
        expected_policy_hash = None
        if model_policy_path.exists():
            expected_policy_hash = report["policy_hash"]
            expected_prompt_hash = prompt_hash
            expected_routes = {
                role: (
                    f"{model_policy['routes'][route_name]['provider']}:"
                    f"{model_policy['routes'][route_name]['model']}"
                )
                for role, route_name in {
                    "production-primary": "primary",
                    "production-independent": "independent",
                    "correction-proposer": "correction_proposer",
                    "correction-verifier-1": "correction_verifier_1",
                    "correction-verifier-2": "correction_verifier_2",
                }.items()
            }
        replayed_lineage = verify_correction_lineage(
            source_path=root / "baseline.owl",
            candidate_path=root / "candidate.owl",
            ledger_path=root / "correction-ledger.json",
            evidence_path=root / "correction-evidence.json",
            schema_path=(
                Path(report_schema_path).parent
                / "ontology-correction.schema.json"
            ),
            minimum_confidence=minimum_confidence,
            expected_policy_hash=expected_policy_hash,
            expected_prompt_hash=expected_prompt_hash,
            expected_routes=expected_routes,
        )
        if replayed_lineage != correction_lineage:
            raise ValueError("correction lineage differs from release report")

    if model_policy_path.exists():
        surveillance_payload = artifacts["surveillance"]["payload"]
        stored_sample = surveillance_payload.get("sample")
        stored_results = surveillance_payload.get("results")
        if not isinstance(stored_sample, dict) or not isinstance(
            stored_results, dict
        ):
            raise ValueError("surveillance evidence lacks sample or votes")
        graph = Graph().parse(root / "candidate.owl", format="xml")
        changed_surveillance_ids = {
            surveillance_record_id(item["after"])
            for item in artifacts["manifest"]["payload"]["records"]
            if item.get("after")
        }
        legacy = build_legacy_records(graph, changed_surveillance_ids)
        replayed_results = {}
        response_validator = Draft202012Validator(schema)
        for record_id, stored in stored_results.items():
            assessments = stored.get("assessments", [])
            if (
                {item.get("role") for item in assessments}
                != {"production-primary", "production-independent"}
                or len(assessments) != 2
            ):
                raise ValueError(
                    "surveillance record lacks two independent votes"
                )
            responses = [
                item["response"] for item in assessments
            ]
            for response in responses:
                response_validator.validate(response)
                if response["record_id"] != record_id:
                    raise ValueError(
                        "surveillance vote record ID mismatch"
                    )
            verdict = (
                "pass"
                if all(
                    item["verdict"] == "pass"
                    and float(item["confidence"]) >= minimum_confidence
                    for item in responses
                )
                else "defect"
            )
            defect_types = sorted({
                defect for response in responses
                for defect in response.get("defect_types", [])
            })
            replayed_results[record_id] = {
                "verdict": verdict,
                "defect_types": defect_types,
            }
            if (
                stored.get("verdict") != verdict
                or stored.get("defect_types") != defect_types
            ):
                raise ValueError(
                    "surveillance summary differs from provider votes"
                )
        sample = select_surveillance_sample(legacy, review_policy)
        while True:
            evaluated = evaluate_surveillance(
                sample, legacy, replayed_results, review_policy
            )
            expansions = {
                name: details["expansion_ids"]
                for name, details in evaluated["strata"].items()
                if details["expansion_ids"]
            }
            if not expansions:
                break
            for name, ids in expansions.items():
                stratum = sample["strata"][name]
                stratum["selected_ids"] = sorted(
                    set(stratum["selected_ids"]) | set(ids)
                )
                stratum["sample_count"] = len(
                    stratum["selected_ids"]
                )
                stratum["census"] = True
        if sample != stored_sample:
            raise ValueError("surveillance sample or expansion differs")
        expected_surveillance = {
            key: value for key, value in surveillance_payload.items()
            if key not in {"sample", "results"}
        }
        if evaluated != expected_surveillance:
            raise ValueError("surveillance decision differs on replay")

    reconstructed = reconcile(
        sorted(manifest_ids), artifacts["primary"], artifacts["independent"],
        minimum_confidence=minimum_confidence,
        expected_candidate_hash=report["candidate_hash"],
        expected_primary_qualification=primary_q["qualification_hash"],
        expected_independent_qualification=independent_q["qualification_hash"],
    )
    if reconstructed["records"] != report["payload"]["record_states"]:
        raise ValueError("record states do not match provider assessments")
    decision = report["payload"]["release_decision"]
    recomputed_pass = (
        report["status"] == "complete"
        and not artifacts["census"]["payload"].get("failures")
        and artifacts["census"]["payload"].get("population_count")
        == artifacts["census"]["payload"].get("inspected_count")
        and all(value == "accepted" for value in report["payload"]["record_states"].values())
        and artifacts["surveillance"]["payload"].get("decision") == "pass"
        and primary_q["status"] == independent_q["status"] == "qualified"
        and reconstructed["status"] == "complete"
    )
    if (decision == "merge_gate_passed") != recomputed_pass:
        raise ValueError("release decision does not match replayed evidence")
    return {"verified": True, "release_decision": decision, "report_hash": report["artifact_hash"]}
