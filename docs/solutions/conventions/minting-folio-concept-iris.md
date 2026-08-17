---
title: Minting FOLIO concept IRIs
date: 2026-08-17
category: conventions
module: ontology-authoring
problem_type: convention
component: tooling
severity: high
applies_when:
  - Adding a new class to FOLIO.owl
  - Reviewing a change that introduces a concept IRI
  - Choosing between FOLIO IRI generators that disagree
tags: [iri, minting, base62, folio-python, webprotege, permanence]
---

# Minting FOLIO concept IRIs

## Context

FOLIO IRIs are permanent — `docs/FOLIO-CHANGE-POLICY.md` §2 states that a
published IRI is never deleted and never reused. Minting is therefore a one-way
door, and an improvised local name is permanent too.

Despite that, the convention was written down nowhere, and three of the four
concepts added by hand during 2026 drifted from every shape in the file. One,
`RtQgrbKIvgHvOXm_6lIpaY172`, is 25 characters — a length nothing else in the
ontology has. It cannot be corrected; §2 forbids that.

Worse, two generators disagree. `folio-python`'s `FOLIOGraph.generate_iri()` is
ALEA's own published client method, and the shape it emits matches **2 of the
18,326** published concepts.

## Guidance

**Generate IRIs. Never type one.**

```bash
python -m pip install -r scripts/requirements-authoring.txt
python scripts/mint_iri.py                  # mint, with sorted insertion point
python scripts/mint_iri.py --check <IRI>    # validate shape and non-collision
python scripts/mint_iri.py --audit          # family census and drift gate
```

**The convention is `R` + base62 of 127 random bits**, e.g.
`R1cNH7TLMiSlSbIbdFsynUk`. Minting emits a 22-character body (the modal length);
validation accepts 19–22 (`MIN_BODY_LENGTH`/`MAX_BODY_LENGTH` in
`scripts/mint_iri.py`), because a shorter body is a legitimate low-probability
output of the same generator and one such IRI, `R92xsHpdHu6BJjtepuRu`, is
already published.

**The algorithm lives upstream, and only upstream.** `scripts/mint_iri.py`
contains no generation logic; it imports `folio.iri` and refuses to run without
it rather than falling back. A fallback generator *is* drift. Even the
validation pattern is built from the upstream prefix and alphabet rather than
restating them. What the repo-side script owns is what upstream cannot know:
collision checking against the working copy including uncommitted edits, the
sorted insertion point, and the family census.

**Every published local name belongs to one of five families**, and only the
first is minted going forward:

| family | count | origin |
|---|---:|---|
| `R` + base62 | 11,428 | SALI/LMSS era; current convention |
| `R` + 23 hex characters | 4,751 | SALI legacy |
| raw base64url of a uuid4, 22 chars | 1,992 | WebProtege |
| `R` + base64url | 151 | mixed |
| bare alphanumeric, terminal `A/Q/g/w` | 2 | folio-python before 0.4.0 |

Two published names match no family and are recorded in `KNOWN_NONCONFORMING`
rather than corrected. `tests/test_iri_minting.py` fails if a third appears.

## Why This Matters

**The 127-bit width is evidence, not a preference.** It was recovered from the
published data, and it is the only surviving record of how these IRIs were
originally generated. Body lengths of 20/21/22 characters occur at
0.39% / 25.75% / 73.85%. Base62 of a uniform 127-bit integer predicts
0.39% / 25.31% / 74.29%. A 128-bit generator predicts 0.21% / 12.9% / 86.9% and
is excluded. Change the width and future IRIs pollute the distribution, after
which the convention can no longer be recovered by anyone. `mint_iri.py` and
the upstream module both pin it with a test.

**Distribution fitting is how you recover an undocumented convention.** Nothing
in the repo or on openlegalstandard.org documents the IRI format. Simulating
each candidate generator 200,000 times and comparing length distributions and
terminal-character variety against the corpus separated the families
decisively — the folio-python model predicts 11.2% of bodies at 20 characters
where the corpus has 0.39%, and only four distinct terminal characters where the
corpus has 62.

**The same method identified which IRIs came from which tool.** Raw WebProtege
output is *always* exactly 22 characters, so a 21-character bare alphanumeric
name cannot be WebProtege's — but it is the second-likeliest folio-python
length. That is how the two 2026 mints were identified as correct tool output
rather than the drift they were first taken for.

**Being the maintainers' published tool does not make a generator authoritative
about the corpus.** `generate_iri()`'s docstring said it approximated
WebProtege, and it does not: WebProtege emits base64url *with* `-` and `_` at a
fixed 22 characters, which is the 1,992-member family. So the shape it produced
matched neither the majority convention nor the tool it named. The right
response was to change the tool to match the corpus, not to adopt an output that
matched 2 concepts.

## When to Apply

- Before adding any class to `FOLIO.owl` — mint, then use the reported sorted
  insertion point.
- When reviewing a change that introduces an IRI — `--check` rejects both a
  non-canonical shape and a name already in use.
- When `folio-python` is upgraded — confirm the installed version still emits
  the `R` + base62 shape.

## Examples

The class this convention was written alongside sits among siblings that all
share the shape, which is the point:

```
Investment Funds     RCzxVprwB3RwZ8EMewt18Jt   (parent)
Hedge Fund           R7e7pNl5IOMFbxKN2GV2C41
Mutual Fund          RCH1NJTVGwEmadkYOldsHtQ
Co-Investment Fund   R1cNH7TLMiSlSbIbdFsynUk   (minted 2026-08-17)
```

What the pre-0.4.0 `generate_iri()` would have produced for that same class:

```
07BzhNmkTx6PPCobTF1ufw
```

Legible as a FOLIO IRI to no one reading the file.

Checking an improvised name fails loudly rather than landing permanently:

```
$ python scripts/mint_iri.py --check cBc5LabSECSyTjKnbRPQA2
family        legacy-webprotege-uuid
canonical     NO
REJECT: not the shape folio.iri emits. Mint it, do not type it.
```

## Related

- `docs/FOLIO-CHANGE-POLICY.md` §2 — IRI permanence; why this is one-way
- `scripts/mint_iri.py` — the repo-side CLI, collision check, and drift gate
- `tests/test_iri_minting.py` — family classification and the drift ratchet
- `scripts/requirements-authoring.txt` — why `folio-python` is not in the
  fail-closed QA requirements
- alea-institute/folio-python#19 — moves `generate_iri()` to this convention and
  adds an `iri` module in that repository as the authority (path is in
  `folio-python`, not this repo). Open as of this writing; until it ships and
  releases as 0.4.0, `mint_iri.py` cannot run against a released
  `folio-python`.
