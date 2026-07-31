#!/usr/bin/env python3
"""Verify a WebProtégé merge output against an accepted hydration ledger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ontology_qa.fidelity import verify_merge_fidelity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webprotege-base", required=True)
    parser.add_argument("--merge-output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        result = verify_merge_fidelity(
            webprotege_base_path=args.webprotege_base,
            merge_output_path=args.merge_output,
            manifest=manifest,
            accepted_states=report["payload"]["record_states"],
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, KeyError, ValueError) as exc:
        print(f"WebProtégé fidelity verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
