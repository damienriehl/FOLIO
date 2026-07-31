from __future__ import annotations

import hashlib
import io
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from safe_extract_evidence_bundle import extract_verified_bundle


def _archive(path: Path, name: str = "evidence/report.json") -> str:
    with tarfile.open(path, "w:gz") as bundle:
        data = b"{}"
        member = tarfile.TarInfo(name)
        member.size = len(data)
        bundle.addfile(member, io.BytesIO(data))
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_verified_archive_extracts_only_evidence_tree(tmp_path):
    archive = tmp_path / "evidence.tgz"
    digest = _archive(archive)
    output = tmp_path / "evidence"
    extract_verified_bundle(archive, output, digest)
    assert (output / "report.json").read_bytes() == b"{}"


def test_digest_mismatch_fails_before_extraction(tmp_path):
    archive = tmp_path / "evidence.tgz"
    _archive(archive)
    with pytest.raises(ValueError, match="digest"):
        extract_verified_bundle(
            archive, tmp_path / "evidence", "sha256:" + "0" * 64
        )


def test_traversal_member_is_rejected(tmp_path):
    archive = tmp_path / "evidence.tgz"
    digest = _archive(archive, "evidence/../../verify_acceptance_handoff.py")
    with pytest.raises(ValueError, match="unsafe"):
        extract_verified_bundle(archive, tmp_path / "evidence", digest)
