# Agreements hidden labels — rebuild off main

Sweep `sweep-2026-10-20`, FOLIO lane.

## Problem

`add-synonyms-appellate-appeal` (`bf78c78`) adds 16 `skos:hiddenLabel` values to
Agreements / Contracts (`R88D8i8AcSTUig2X3yPbFHg`). The branch sits 18 commits
behind `main`; the staged-change census (`docs/2026-08-05-staged-change-census.md`
on `docs/change-policy`) flagged six of the sixteen:

- `Agreement`, `Contract` — already `skos:altLabel` on the same class since
  `e36f3f8`; repeating them as `hiddenLabel` violates SKOS S13.
- `Covenant`, `Indenture` — already resolve to `Obligation` and `Indenture`;
  adding them here recreates the `e36f3f8` precision bug.
- `Covenants`, `Indentures` — plurals of those concept names; same risk.

## Plan

1. Branch fresh off `main` rather than merging the stale branch.
2. Add the clean terms: Accord(s), Pact(s), Compact(s).
3. Verify: ground-triple diff is +6/−0; no case-insensitive collision with any
   `rdfs:label`/`prefLabel`/`altLabel`/`hiddenLabel` on another concept.
4. Regenerate `FOLIO-webprotege-merge-output.owl`.

## Found during step 4

`scripts/generate_webprotege_merge.py` propagated new `altLabel`s on existing
classes but silently dropped new `hiddenLabel`s; the summary never mentioned
them. The output would never carry the change. Fix: detect and insert new
`hiddenLabel`s through the same path as `altLabel`s, and insert at the start of
the `</owl:Class>` line so new lines keep the file's indentation. Tests in
`tests/test_webprotege_label_additions.py`.

## Code review pass

- Dropped `Concordat(s)` (a treaty by definition; `Treaties` sits under Legal
  Authorities, outside Agreements) and `Undertaking(s)` (legal sense is usually
  a promise, i.e. `Obligation`; in EU law, an enterprise). Filed for Damien.
- A move between `altLabel` and `hiddenLabel` now removes the old slot instead
  of keeping both (S13). Removal stays suppressed for strings that moved to
  `rdfs:label`/`prefLabel` or were re-tagged within the same predicate.
- Label insertion falls back to right-before-`</owl:Class>` when the closing
  tag shares a line with other content.
- `.github/workflows/tests.yml` runs `pytest` on pull requests and `main`.

## Left open

- The stale `add-synonyms-appellate-appeal` branch stays on the remote;
  deleting it is Damien's call (it carries nothing this PR does not).
- OntoKit does not index `skos:hiddenLabel` (census §4), so these labels reach
  WebProtégé and RDF consumers but not FOLIO's own viewer search yet.
