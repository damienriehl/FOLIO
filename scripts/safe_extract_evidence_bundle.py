#!/usr/bin/env python3
"""Verify and safely extract a signed ontology-QA evidence archive."""

from __future__ import annotations

import argparse
import hashlib
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


def extract_verified_bundle(
    archive: str | Path, output: str | Path, expected_digest: str
) -> None:
    archive = Path(archive)
    output = Path(output)
    actual = "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected_digest:
        raise ValueError("evidence archive digest mismatch")
    if output.exists():
        raise FileExistsError(f"evidence output already exists: {output}")
    with tarfile.open(archive, mode="r:gz") as bundle:
        members = bundle.getmembers()
        if not members:
            raise ValueError("evidence archive is empty")
        for member in members:
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or path.parts[0] != "evidence"
                or not (member.isdir() or member.isfile())
            ):
                raise ValueError(
                    f"unsafe evidence archive member: {member.name}"
                )
        with tempfile.TemporaryDirectory(
            prefix="folio-evidence-", dir=output.parent
        ) as directory:
            staging = Path(directory)
            bundle.extractall(staging, members=members, filter="data")
            extracted = staging / "evidence"
            if not extracted.is_dir():
                raise ValueError("evidence archive lacks evidence directory")
            extracted.replace(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--expected-digest", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    extract_verified_bundle(
        args.archive, args.output, args.expected_digest
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
