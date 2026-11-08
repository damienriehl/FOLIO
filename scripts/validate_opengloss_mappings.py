#!/usr/bin/env python3
"""Validate an OpenGloss SSSOM mapping set independently of its writer."""
from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET

import yaml

from opengloss_mapping.validate import Finding, read_mapping_set, validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--folio")
    args = parser.parse_args()
    rows = []
    try:
        header, rows = read_mapping_set(args.path)
        findings = validate(header, rows, args.folio)
    except (OSError, ValueError, yaml.YAMLError, ET.ParseError) as error:
        findings = [Finding("parse", str(error))]
    for finding in findings:
        print(f"{finding.code}: {finding.message}")
    print(f"FAIL: {len(findings)} findings" if findings else f"OK: {len(rows)} rows")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
