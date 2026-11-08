"""Deterministic reporting for the fixed offline ontology QA canary."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml

from .qualification import ROLES, validate_role_separation
from .records import canonical_json, content_hash

SCHEMA_VERSION = "folio-offline-readiness/v1"

PROFILE = {
    "deterministic-fixtures": ["tests/test_annotation_validators.py", "tests/test_hydration_delta.py"],
    "qualification-rules": ["tests/test_model_qualification.py", "tests/test_model_evals.py"],
    "release-decisions": ["tests/test_hydration_qa_pipeline.py"],
    "replay-and-lineage": ["tests/test_evidence_replay.py"],
    "full-policy-fixture": ["tests/test_trusted_changed_record_corrections.py"],
    "workflow-contracts": ["tests/test_workflow_contract.py"],
}

MANDATORY = (
    "test_baseline_debt_is_reported_but_only_new_failures_block",
    "test_manifest_is_byte_stable_and_self_hashed",
    "test_production_votes_must_use_different_providers",
    "test_expired_or_mismatched_qualification_blocks",
    "test_frozen_controls_cover_every_policy_slice",
    "test_quarantine_or_incomplete_stage_blocks",
    "test_stale_candidate_hash_blocks_and_marks_report_stale",
    "test_tampered_evidence_fails_replay",
    "test_fresh_sha_bundle_replays_correction_source_lineage",
    "test_trusted_runner_accepts_with_stubbed_independent_providers",
    "test_failed_validation_publishes_no_correction_artifacts",
    "test_pr_path_has_no_secret_bearing_model_step",
    "test_trigger_never_combines_slurp_with_jq",
    "test_trigger_dispatch_names_repository",
    "test_webprotege_requires_signature_and_offline_replay",
)

INPUT_GLOBS = (
    "scripts/ontology_qa/*.py", "scripts/run_ontology_hydration_qa.py",
    "scripts/run_trusted_ontology_qa.py", "scripts/requirements.txt", "schemas/*",
    "qa/ontology/**/*", ".github/workflows/*.yml",
    *(path for paths in PROFILE.values() for path in paths),
)


def input_identity(root: Path) -> dict[str, Any]:
    paths: set[Path] = set()
    for pattern in INPUT_GLOBS:
        paths.update(path for path in root.glob(pattern) if path.is_file())
    files = {path.relative_to(root).as_posix(): content_hash(path.read_bytes()) for path in sorted(paths)}
    dependencies = {}
    for name in ("pytest", "PyYAML", "rdflib", "jsonschema", "cryptography"):
        try:
            dependencies[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies[name] = "missing"
    value = {
        "files": files,
        "profile": PROFILE,
        "mandatory_proofs": list(MANDATORY),
        "runtime": {"implementation": platform.python_implementation(), "python": platform.python_version()},
        "dependencies": dependencies,
    }
    return {"fingerprint": content_hash(canonical_json(value)), **value}


def route_observation(root: Path) -> dict[str, Any]:
    try:
        policy = yaml.safe_load((root / "qa/ontology/model-policy.yaml").read_text())
        route_names = {
            "production-primary": "primary", "production-independent": "independent",
            "benchmark-adjudicator": "benchmark_adjudicator",
            "correction-proposer": "correction_proposer",
            "correction-verifier-1": "correction_verifier_1",
            "correction-verifier-2": "correction_verifier_2",
        }
        observations = []
        for role in sorted(ROLES):
            route = policy.get("routes", {}).get(route_names[role], {})
            provider, model = route.get("provider"), route.get("model")
            if not provider or not model:
                raise ValueError(f"missing provider or model for {role}")
            observations.append({"role": role, "provider": provider, "route_id": f"{provider}:{model}"})
        validate_role_separation(observations)
        return {"status": "passed", "roles": observations}
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        return {"status": "incomplete", "error": str(exc)}


def read_junit(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    outcomes: dict[str, str] = {}
    for case in root.iter("testcase"):
        identity = f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name', '')}"
        if list(case.iter("skipped")):
            outcome = "skipped"
        elif list(case.iter("failure")) or list(case.iter("error")):
            outcome = "failed"
        else:
            outcome = "passed"
        if identity in outcomes:
            raise ValueError(f"duplicate JUnit identity: {identity}")
        outcomes[identity] = outcome
    return outcomes


def build_report(*, identity: dict[str, Any], receipt: dict[str, Any] | None,
                 junit: dict[str, str] | None, process_exit: int | None,
                 routes: dict[str, Any], extra_issues: list[str] | None = None) -> dict[str, Any]:
    issues = list(extra_issues or [])
    collected = receipt.get("collected", []) if receipt else []
    outcomes = receipt.get("outcomes", {}) if receipt else {}
    if not receipt or junit is None:
        issues.append("structured execution evidence is missing or malformed")
    if len(collected) != len(set(collected)):
        issues.append("collection contains duplicate identities")
    if set(collected) != set(outcomes) or (junit is not None and set(collected) != set(junit)):
        issues.append("collection and terminal outcomes do not agree")
    selected_files = {path for paths in PROFILE.values() for path in paths}
    observed_files = {node.split("::", 1)[0] for node in collected}
    for path in sorted(selected_files - observed_files):
        issues.append(f"selected file did not execute: {path}")
    for proof in MANDATORY:
        if not any(node.split("[")[0].endswith(f"::{proof}") for node in collected):
            issues.append(f"mandatory proof missing: {proof}")
    if routes.get("status") != "passed":
        issues.append("configured route structure did not pass")
    forbidden = {"skipped", "xfailed", "xpassed"}
    if any(value in forbidden for value in outcomes.values()):
        issues.append("selected cases include skipped or expected-failure outcomes")
    failures = sorted(node for node, result in outcomes.items() if result == "failed")
    if process_exit not in (0, 1):
        issues.append(f"pytest did not terminate with an assertion outcome (exit {process_exit})")
    status = "incomplete" if issues else ("failed" if failures or process_exit == 1 else "passed")
    groups = []
    for name, files in sorted(PROFILE.items()):
        nodes = sorted(node for node in collected if node.split("::", 1)[0] in files)
        groups.append({"group": name, "files": files, "executed": len(nodes),
                       "failed": sum(outcomes.get(node) == "failed" for node in nodes)})
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_scope": "offline_test_suite",
        "offline_status": status,
        "live_qualification": "not_run",
        "live_actions": "not_verified",
        "release_authorization": False,
        "input_identity": identity,
        "route_structure": routes,
        "coverage": groups,
        "observed": {"collected": len(collected), "failed": failures},
        "issues": sorted(set(issues)),
    }


def markdown(report: dict[str, Any]) -> bytes:
    lines = [
        "# Offline ontology QA readiness", "",
        f"**Offline status:** `{report['offline_status']}`", "",
        "This report covers deterministic offline test evidence only. It does not evaluate live provider qualification, live GitHub Actions configuration, current ontology quality, or release authorization.", "",
        f"- Live provider qualification: `{report['live_qualification']}`",
        f"- Live Actions configuration: `{report['live_actions']}`",
        f"- Release authorized: `{str(report['release_authorization']).lower()}`",
        f"- Input fingerprint: `{report['input_identity']['fingerprint']}`", "", "## Coverage", "",
    ]
    lines += [f"- {g['group']}: {g['executed']} executed, {g['failed']} failed" for g in report["coverage"]]
    lines += ["", "## Issues", ""]
    lines += ([f"- {issue}" for issue in report["issues"]] or ["- None."])
    return ("\n".join(lines) + "\n").encode()


def atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)
