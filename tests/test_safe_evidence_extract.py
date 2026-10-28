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


def _members_archive(path: Path, members: list[tarfile.TarInfo]) -> str:
    with tarfile.open(path, "w:gz") as bundle:
        for member in members:
            data = b"{}" if member.isfile() else None
            if data is not None:
                member.size = len(data)
            bundle.addfile(member, io.BytesIO(data) if data is not None else None)
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


@pytest.mark.parametrize(
    "member",
    [
        tarfile.TarInfo("/evidence/report.json"),
        tarfile.TarInfo("other/report.json"),
        tarfile.TarInfo("evidence/link"),
        tarfile.TarInfo("evidence/hardlink"),
        tarfile.TarInfo("evidence/device"),
    ],
)
def test_unsafe_member_types_and_roots_publish_nothing(tmp_path, member):
    if member.name.endswith("/link"):
        member.type = tarfile.SYMTYPE
        member.linkname = "report.json"
    elif member.name.endswith("hardlink"):
        member.type = tarfile.LNKTYPE
        member.linkname = "evidence/report.json"
    elif member.name.endswith("device"):
        member.type = tarfile.CHRTYPE
    archive = tmp_path / "evidence.tgz"
    digest = _members_archive(archive, [member])
    output = tmp_path / "published"
    with pytest.raises(ValueError, match="unsafe"):
        extract_verified_bundle(archive, output, digest)
    assert not output.exists()


def test_late_unsafe_member_does_not_publish_early_valid_member(tmp_path):
    archive = tmp_path / "evidence.tgz"
    unsafe = tarfile.TarInfo("evidence/../../escaped")
    digest = _members_archive(
        archive, [tarfile.TarInfo("evidence/report.json"), unsafe]
    )
    output = tmp_path / "published"
    with pytest.raises(ValueError, match="unsafe"):
        extract_verified_bundle(archive, output, digest)
    assert not output.exists()
    assert not (tmp_path / "escaped").exists()


def test_empty_corrupt_and_non_directory_evidence_publish_nothing(tmp_path):
    empty = tmp_path / "empty.tgz"
    with tarfile.open(empty, "w:gz"):
        pass
    corrupt = tmp_path / "corrupt.tgz"
    corrupt.write_bytes(b"not a tar archive")
    evidence_file = tmp_path / "file.tgz"
    digest_file = _archive(evidence_file, "evidence")
    cases = [
        (empty, "sha256:" + hashlib.sha256(empty.read_bytes()).hexdigest()),
        (corrupt, "sha256:" + hashlib.sha256(corrupt.read_bytes()).hexdigest()),
        (evidence_file, digest_file),
    ]
    for index, (archive, digest) in enumerate(cases):
        output = tmp_path / f"output-{index}"
        with pytest.raises((ValueError, tarfile.TarError)):
            extract_verified_bundle(archive, output, digest)
        assert not output.exists()


def test_existing_destination_is_preserved(tmp_path):
    archive = tmp_path / "evidence.tgz"
    digest = _archive(archive)
    output = tmp_path / "evidence"
    output.mkdir()
    sentinel = output / "sentinel"
    sentinel.write_bytes(b"unchanged")
    with pytest.raises(FileExistsError):
        extract_verified_bundle(archive, output, digest)
    assert sentinel.read_bytes() == b"unchanged"
