"""Canonical records and artifact hashing for ontology QA."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

ABSENT_HASH = hashlib.sha256(b"<absent>").hexdigest()
SCHEMA_VERSION = "folio-hydration-delta/v1"


def canonical_text(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def content_hash(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class AnnotationValue:
    subject: str
    predicate: str
    lexical: str
    object_kind: str = "literal"
    language: str | None = None
    datatype: str | None = None

    def canonical(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object_kind": self.object_kind,
            "language": self.language.lower() if self.language else None,
            "datatype": self.datatype,
            "lexical": canonical_text(self.lexical),
        }

    @property
    def value_hash(self) -> str:
        return content_hash(canonical_json(self.canonical()))

    @property
    def locator(self) -> dict[str, Any]:
        value = self.canonical()
        value.pop("lexical")
        return value


@dataclass(frozen=True)
class DeltaRecord:
    change: str
    locator: dict[str, Any]
    before: AnnotationValue | None
    after: AnnotationValue | None

    def canonical(self) -> dict[str, Any]:
        before = self.before.canonical() if self.before else None
        after = self.after.canonical() if self.after else None
        identity = {
            "locator": self.locator,
            "before_hash": self.before.value_hash if self.before else ABSENT_HASH,
            "after_hash": self.after.value_hash if self.after else ABSENT_HASH,
        }
        return {
            "record_id": content_hash(canonical_json(identity)),
            "change": self.change,
            "locator": self.locator,
            "before_hash": identity["before_hash"],
            "after_hash": identity["after_hash"],
            "before": before,
            "after": after,
        }


def artifact_envelope(
    *,
    payload: dict[str, Any],
    run_id: str,
    attempt_id: str,
    parent_hashes: list[str],
    baseline_hash: str,
    candidate_hash: str,
    policy_hash: str,
    tool_hash: str,
    status: str,
    schema_version: str = SCHEMA_VERSION,
) -> dict[str, Any]:
    envelope = {
        "schema_version": schema_version,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "parent_hashes": sorted(parent_hashes),
        "baseline_hash": baseline_hash,
        "candidate_hash": candidate_hash,
        "policy_hash": policy_hash,
        "tool_hash": tool_hash,
        "status": status,
        "payload": payload,
    }
    return {"artifact_hash": content_hash(canonical_json(envelope)), **envelope}
