#!/usr/bin/env python3
"""Apply a verified correction ledger as one copy-on-write transaction."""

import argparse
import json
import sys
from pathlib import Path

from ontology_qa.corrections import apply_correction_batch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("ledger")
    parser.add_argument("output")
    args = parser.parse_args()
    try:
        corrections = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
        result = apply_correction_batch(args.source, args.output, corrections)
        print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"correction transaction failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
