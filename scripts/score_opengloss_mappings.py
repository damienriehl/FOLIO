#!/usr/bin/env python3
"""Report mapping precision, recall, and predicate agreement on judged pairs."""
from __future__ import annotations

import argparse
import json
import sys

import yaml

from opengloss_mapping.score import read_gold, score
from opengloss_mapping.validate import read_mapping_set


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tsv")
    parser.add_argument("--gold", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        _, rows = read_mapping_set(args.tsv)
        result = score(rows, read_gold(args.gold))
    except (OSError, ValueError, KeyError, yaml.YAMLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
