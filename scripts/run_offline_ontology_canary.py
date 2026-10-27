#!/usr/bin/env python3
"""Run the fixed, credential-free ontology QA readiness profile."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from ontology_qa.offline_canary import (
    PROFILE, atomic_write, build_report, input_identity, markdown, read_junit,
    route_observation,
)
from ontology_qa.records import canonical_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output_dir.absolute()
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error(f"output destination already exists: {destination}")
    raw = destination / "raw"
    raw.mkdir()
    receipt_path, junit_path = raw / "receipt.json", raw / "junit.xml"
    before = input_identity(ROOT)
    env = {
        "PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"), "LC_ALL": "C.UTF-8",
        "PYTHONPATH": os.pathsep.join((str(ROOT / "tests"), str(ROOT / "scripts"))),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "FOLIO_OFFLINE_RECEIPT": str(receipt_path),
    }
    files = [path for paths in PROFILE.values() for path in paths]
    command = [sys.executable, "-m", "pytest", "-p", "offline_canary_plugin",
               "--junitxml", str(junit_path), "-q", *files]
    issues: list[str] = []
    exit_code = None
    with (raw / "pytest.log").open("wb") as log:
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=600, check=False)
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            issues.append("pytest exceeded the 600-second timeout")
        except OSError as exc:
            issues.append(f"pytest could not start: {exc}")
    receipt = junit = None
    try:
        receipt = json.loads(receipt_path.read_text())
        junit = read_junit(junit_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(f"execution receipt unavailable: {exc}")
    after = input_identity(ROOT)
    if before["fingerprint"] != after["fingerprint"]:
        issues.append("fingerprinted inputs changed during execution")
    report = build_report(identity=before, receipt=receipt, junit=junit,
                          process_exit=exit_code, routes=route_observation(ROOT),
                          extra_issues=issues)
    try:
        atomic_write(destination / "report.json", canonical_json(report) + b"\n")
        atomic_write(destination / "summary.md", markdown(report))
    except OSError as exc:
        print(f"could not publish readiness report: {exc}", file=sys.stderr)
        return 2
    print(f"Offline ontology QA: {report['offline_status']} ({destination})")
    return {"passed": 0, "failed": 1, "incomplete": 2}[report["offline_status"]]


if __name__ == "__main__":
    raise SystemExit(main())
