#!/usr/bin/env python3
"""Mint, check, and audit FOLIO concept IRIs.

FOLIO concept IRIs are permanent (``docs/FOLIO-CHANGE-POLICY.md`` §2): once
published, one is never deleted and never reused. That makes minting a one-way
door, and it makes an improvised local name permanent too. This script exists so
that new IRIs are generated rather than typed.

**This script contains no IRI generation logic of its own.** The algorithm lives
upstream in ``folio-python`` (``folio/iri.py``), which is ALEA's own client for
FOLIO and therefore the right place for it. Carrying a second implementation
here would mean two things to keep in step, and no way to notice when they drift
apart. What this script adds is the part upstream cannot know about:

* collision checking against the working copy of the ontology, including
  uncommitted local edits, rather than against a published release;
* the sorted insertion point, since ``FOLIO.owl`` is serialised in local-name
  order;
* a census of the historical IRI families, and a ratchet against new drift.

Requires ``folio-python`` with the ``folio.iri`` module::

    pip install 'folio-python>=0.4.0'

Usage::

    python scripts/mint_iri.py                     # mint one IRI
    python scripts/mint_iri.py --count 3           # mint three
    python scripts/mint_iri.py --check RXyz...     # validate one IRI
    python scripts/mint_iri.py --audit             # family census + drift gate

Historical families
-------------------
Measured over the 18,325 ``owl:Class`` declarations at ``8ebf17b``:

==========================================  ======  =====================
family                                      count   origin
==========================================  ======  =====================
``R`` + base62                              11,427  SALI/LMSS era; current
``R`` + 23 hex characters                    4,751  SALI legacy
raw base64url of a uuid4, 22 characters      1,992  WebProtege
``R`` + base64url                              151  mixed
bare alphanumeric, terminal ``A/Q/g/w``          2  folio-python < 0.4.0
==========================================  ======  =====================

Only ``R`` + base62 is minted going forward. The other families are published
and permanent; they are recognised so that the drift gate does not fire on them.
"""

from __future__ import annotations

import argparse
import bisect
import re
import sys
from collections import Counter
from pathlib import Path

try:
    from folio.iri import (
        BASE62_ALPHABET,
        FOLIO_NAMESPACE,
        IRI_PREFIX,
        generate_iri,
    )
except ImportError as exc:  # pragma: no cover - exercised by the install path
    try:
        import folio as _folio

        _detail = (
            f"folio-python {getattr(_folio, '__version__', '?')} is installed but has "
            "no folio.iri module; that arrived in 0.4.0 with the R + base62 change"
        )
    except ImportError:
        _detail = "folio-python is not installed"
    # ImportError, not SystemExit: this module must stay importable-or-skippable
    # by test collectors, and a missing dependency is exactly what ImportError
    # means.
    raise ImportError(
        f"cannot mint: {_detail}. Install it with:\n"
        "  pip install 'folio-python>=0.4.0'\n"
        "This script deliberately has no fallback generator: a second "
        "implementation would drift from the upstream one without anyone noticing."
    ) from exc

#: Accepted body lengths. 127 bits encodes to 22 base62 digits ~74% of the time
#: and 21 ~25%; shorter is rare but legitimate, and ``R92xsHpdHu6BJjtepuRu`` is
#: already published.
MIN_BODY_LENGTH = 19
MAX_BODY_LENGTH = 22

#: Derived from the upstream alphabet rather than restated, so that a change to
#: the generator's alphabet cannot silently pass validation here.
_BODY = f"[{re.escape(BASE62_ALPHABET)}]{{{MIN_BODY_LENGTH},{MAX_BODY_LENGTH}}}"
CANONICAL = re.compile(re.escape(IRI_PREFIX) + _BODY + r"\Z")

LEGACY_HEX = re.compile(r"R[0-9A-Fa-f]{23}\Z")
LEGACY_R_BASE64URL = re.compile(r"R[0-9A-Za-z_-]{19,23}\Z")
LEGACY_WEBPROTEGE_UUID = re.compile(r"[0-9A-Za-z_-]{22}\Z")
#: base64url of exactly 16 bytes always ends in one of these.
LEGACY_FOLIO_PYTHON = re.compile(r"[0-9A-Za-z]{17,21}[AQgw]\Z")

#: Any local name in the namespace, class or not. Deliberately over-inclusive:
#: a collision check must be conservative.
LOCAL_NAME = re.compile(re.escape(FOLIO_NAMESPACE) + r"([0-9A-Za-z_.#+-]+)")
CLASS_IRI = re.compile(
    r'<owl:Class rdf:about="' + re.escape(FOLIO_NAMESPACE) + r'([^"]+)">'
)

#: Published local names matching no family. Permanent per §2; never extend.
#: ``#GovB-US-FD-DHS-HSARPA`` is a government body code, not a minted IRI.
#: ``RtQgrbKIvgHvOXm_6lIpaY172`` was hand-typed in the Refund commit (ea7908a);
#: it is 25 characters, a length nothing else in the ontology has.
KNOWN_NONCONFORMING = frozenset(
    {
        "#GovB-US-FD-DHS-HSARPA",
        "RtQgrbKIvgHvOXm_6lIpaY172",
    }
)

DEFAULT_ONTOLOGIES = (
    "FOLIO.owl",
    "FOLIO-webprotege-merge.owl",
    "FOLIO-webprotege-merge-output.owl",
)

FAMILIES = (
    "canonical (R + base62)",
    "legacy-hex",
    "legacy-r-base64url",
    "legacy-webprotege-uuid",
    "legacy-folio-python",
    "nonconforming",
)


def is_canonical(local_name: str) -> bool:
    """Whether a local name matches what the upstream generator emits."""
    return CANONICAL.fullmatch(local_name) is not None


def iri_family(local_name: str) -> str:
    """Classify a local name. Order matters; the families overlap.

    A bare 22-character base64url UUID may legitimately begin with ``R``, so
    R-prefixed families are tested first. Only ``canonical`` and
    ``nonconforming`` carry weight; the rest are descriptive.
    """
    if is_canonical(local_name):
        return "canonical (R + base62)"
    if LEGACY_HEX.fullmatch(local_name):
        return "legacy-hex"
    if local_name.startswith("R") and LEGACY_R_BASE64URL.fullmatch(local_name):
        return "legacy-r-base64url"
    if LEGACY_WEBPROTEGE_UUID.fullmatch(local_name):
        return "legacy-webprotege-uuid"
    if LEGACY_FOLIO_PYTHON.fullmatch(local_name):
        return "legacy-folio-python"
    return "nonconforming"


def resolve_ontologies(root: Path, given: list[str] | None) -> list[Path]:
    """Ontology files to check for collisions, skipping ones not present."""
    if given:
        return [Path(item) for item in given]
    return [root / name for name in DEFAULT_ONTOLOGIES if (root / name).is_file()]


def collect_used(paths: list[Path]) -> set[str]:
    """Every local name already used in the FOLIO namespace, of any kind.

    Not only ``owl:Class`` subjects: properties, individuals, and restriction
    targets share the namespace, and an IRI colliding with any of them is
    unusable. Both the bare and full spellings are returned, so the result can
    be handed straight to the upstream generator.
    """
    used: set[str] = set()
    for path in paths:
        used.update(LOCAL_NAME.findall(path.read_text(encoding="utf-8")))
    return used | {f"{FOLIO_NAMESPACE}{name}" for name in used}


def class_local_names(path: Path) -> list[str]:
    """Local names of ``owl:Class`` declarations, in document order."""
    return CLASS_IRI.findall(path.read_text(encoding="utf-8"))


def sorted_neighbours(
    local_name: str, class_names: list[str]
) -> tuple[str | None, str | None]:
    """The IRIs a new local name sorts between in the serialisation.

    ``FOLIO.owl`` is emitted in sorted local-name order, with a handful of
    pre-existing collation inversions, so a new class belongs at this position.
    """
    ordered = sorted(name for name in class_names if not name.startswith("#"))
    index = bisect.bisect_left(ordered, local_name)
    return (
        ordered[index - 1] if index > 0 else None,
        ordered[index] if index < len(ordered) else None,
    )


def comment_line_number(path: Path, local_name: str) -> int | None:
    """1-indexed line of the ``<!-- IRI -->`` marker preceding a class."""
    marker = f"<!-- {FOLIO_NAMESPACE}{local_name} -->"
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if marker in line:
                return number
    return None


def run_mint(args: argparse.Namespace, root: Path) -> int:
    paths = resolve_ontologies(root, args.ontology)
    if not paths:
        print("no ontology files found; pass --ontology", file=sys.stderr)
        return 2
    used = collect_used(paths)
    primary = paths[0]
    class_names = class_local_names(primary)
    print(f"checked {len(used) // 2} existing local names across {len(paths)} file(s)")
    for _ in range(args.count):
        iri = generate_iri(used)
        local_name = iri[len(FOLIO_NAMESPACE) :]
        used.add(local_name)
        used.add(iri)
        before, after = sorted_neighbours(local_name, class_names)
        line = comment_line_number(primary, after) if after else None
        print()
        print(iri)
        print(f"  family        {iri_family(local_name)}")
        print(f"  sorts after   {before}")
        print(
            f"  sorts before  {after}" + (f"  ({primary.name}:{line})" if line else "")
        )
    return 0


def run_check(args: argparse.Namespace, root: Path) -> int:
    local_name = args.check.rsplit("/", 1)[-1]
    paths = resolve_ontologies(root, args.ontology)
    used = collect_used(paths) if paths else set()
    taken = local_name in used
    print(f"local name    {local_name}")
    print(f"family        {iri_family(local_name)}")
    print(f"canonical     {'yes' if is_canonical(local_name) else 'NO'}")
    print(f"already used  {'YES' if taken else 'no'}")
    if taken:
        print("REJECT: already published; reuse is forbidden (policy §2).")
        return 1
    if not is_canonical(local_name):
        print("REJECT: not the shape folio.iri emits. Mint it, do not type it.")
        return 1
    print("OK: canonical shape, not yet used.")
    return 0


def run_audit(args: argparse.Namespace, root: Path) -> int:
    paths = resolve_ontologies(root, args.ontology)
    if not paths:
        print("no ontology files found; pass --ontology", file=sys.stderr)
        return 2
    primary = paths[0]
    names = class_local_names(primary)
    counts = Counter(iri_family(name) for name in names)
    print(f"{primary.name}: {len(names)} owl:Class declarations")
    for family in FAMILIES:
        print(f"  {family:<24} {counts.get(family, 0)}")
    unexpected = sorted(
        {name for name in names if iri_family(name) == "nonconforming"}
        - KNOWN_NONCONFORMING
    )
    if unexpected:
        print()
        print("DRIFT: local names matching no family and not previously known:")
        for name in unexpected:
            print(f"  {name}")
        return 1
    print()
    print("no new drift: every nonconforming local name is a known legacy IRI")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--count", type=int, default=1, help="number of IRIs to mint (default 1)"
    )
    parser.add_argument(
        "--ontology",
        action="append",
        help="ontology file to check for collisions; repeatable "
        "(default: the FOLIO OWL files at the repository root)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", metavar="IRI", help="validate an IRI or local name")
    mode.add_argument("--audit", action="store_true", help="IRI family census")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.check:
        return run_check(args, root)
    if args.audit:
        return run_audit(args, root)
    return run_mint(args, root)


if __name__ == "__main__":
    raise SystemExit(main())
