#!/usr/bin/env python3
"""Generate a canonical semantic hydration-delta manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ontology_qa.delta import build_hydration_manifest, manifest_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--baseline-sha")
    parser.add_argument("--candidate-sha")
    args = parser.parse_args()
    try:
        manifest = build_hydration_manifest(
            args.baseline,
            args.candidate,
            run_id=args.run_id,
            attempt_id=args.attempt_id,
            baseline_sha=args.baseline_sha,
            candidate_sha=args.candidate_sha,
        )
        Path(args.output).write_bytes(manifest_bytes(manifest))
    except (OSError, ValueError) as exc:
        print(f"hydration delta failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
