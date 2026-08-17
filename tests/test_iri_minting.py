"""Repo-side IRI tests.

The generator itself is tested upstream in folio-python (``tests/test_iri.py``);
duplicating those assertions here would be the same drift this repo is trying to
avoid. What is tested here is what upstream cannot see: the published families
in this working copy, and the ratchet against new drift.

Everything here needs ``folio-python>=0.4.0`` because ``scripts/mint_iri.py``
imports it and deliberately has no fallback generator.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

# Skip on the real dependency rather than on mint_iri itself, so that an actual
# breakage in mint_iri surfaces as an error instead of a silent skip.
pytest.importorskip(
    "folio.iri",
    reason="requires folio-python>=0.4.0 (pip install 'folio-python>=0.4.0')",
)
import mint_iri  # noqa: E402

ROOT = Path(__file__).parents[1]
ONTOLOGY = ROOT / "FOLIO.owl"

requires_ontology = pytest.mark.skipif(
    not ONTOLOGY.is_file(), reason="FOLIO.owl not present"
)


@pytest.mark.parametrize(
    ("local_name", "family"),
    [
        ("RCzxVprwB3RwZ8EMewt18Jt", "canonical (R + base62)"),  # Investment Funds
        ("R7e7pNl5IOMFbxKN2GV2C41", "canonical (R + base62)"),  # Hedge Fund
        ("R92xsHpdHu6BJjtepuRu", "canonical (R + base62)"),  # shortest published
        ("R001c1c1AB6bb45501c7624c", "legacy-hex"),
        ("R-AccZ4Q5TtG0liq9b7miEA", "legacy-r-base64url"),
        ("A35ng-FGRcus0Cc0pYFhYA", "legacy-webprotege-uuid"),
        ("cBc5LabSECSyTjKnbRPQA", "legacy-folio-python"),  # Risk Capacity
        ("50Hs2QBS3KQkNd48DLU5g", "legacy-folio-python"),  # Risk Tolerance
        ("RtQgrbKIvgHvOXm_6lIpaY172", "nonconforming"),  # Refund, hand-typed
        ("#GovB-US-FD-DHS-HSARPA", "nonconforming"),  # government body code
    ],
)
def test_family_classification(local_name: str, family: str) -> None:
    assert mint_iri.iri_family(local_name) == family


def test_canonical_pattern_is_derived_from_upstream() -> None:
    """The accepted shape must track folio.iri, not restate it.

    If upstream changed its alphabet or prefix and this repo hardcoded the old
    one, freshly minted IRIs would fail validation here -- or worse, pass.
    """
    from folio.iri import BASE62_ALPHABET, IRI_PREFIX

    assert mint_iri.CANONICAL.pattern.startswith(IRI_PREFIX)
    for digit in BASE62_ALPHABET:
        assert mint_iri.is_canonical(IRI_PREFIX + digit * 22)


def test_upstream_output_is_accepted_here() -> None:
    """Whatever folio.iri mints must classify as canonical in this repo."""
    from folio.iri import FOLIO_NAMESPACE, generate_iri

    for _ in range(200):
        local_name = generate_iri()[len(FOLIO_NAMESPACE) :]
        assert mint_iri.is_canonical(local_name), local_name
        assert mint_iri.iri_family(local_name) == "canonical (R + base62)"


@requires_ontology
def test_published_class_iris_do_not_drift() -> None:
    """Ratchet: no new local name may match none of the known families.

    IRIs are permanent, so the two published outliers cannot be corrected --
    they are recorded instead. This fails the moment a third appears, which is
    the only point at which it is still cheap to fix.
    """
    names = mint_iri.class_local_names(ONTOLOGY)
    nonconforming = {
        name for name in names if mint_iri.iri_family(name) == "nonconforming"
    }
    assert nonconforming == set(mint_iri.KNOWN_NONCONFORMING)


@requires_ontology
def test_class_iris_are_unique() -> None:
    names = mint_iri.class_local_names(ONTOLOGY)
    assert len(names) == len(set(names))


@requires_ontology
def test_minting_avoids_every_published_local_name() -> None:
    from folio.iri import generate_iri

    used = mint_iri.collect_used([ONTOLOGY])
    assert "RCzxVprwB3RwZ8EMewt18Jt" in used
    assert "https://folio.openlegalstandard.org/RCzxVprwB3RwZ8EMewt18Jt" in used
    assert not {generate_iri(used) for _ in range(10)} & used


@requires_ontology
def test_sorted_neighbours_bracket_a_fresh_name() -> None:
    from folio.iri import FOLIO_NAMESPACE, generate_iri

    names = mint_iri.class_local_names(ONTOLOGY)
    fresh = generate_iri(mint_iri.collect_used([ONTOLOGY]))[len(FOLIO_NAMESPACE) :]
    before, after = mint_iri.sorted_neighbours(fresh, names)
    assert before is not None and before < fresh
    assert after is not None and after > fresh
    assert not any(before < name < after for name in names if name != fresh)


@requires_ontology
def test_co_investment_fund_is_present_and_well_formed() -> None:
    """The class this tooling was built alongside."""
    names = mint_iri.class_local_names(ONTOLOGY)
    assert "R1cNH7TLMiSlSbIbdFsynUk" in names
    assert mint_iri.iri_family("R1cNH7TLMiSlSbIbdFsynUk") == "canonical (R + base62)"
