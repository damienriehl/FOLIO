---
title: "Sweep 2026-10-20 — FOLIO cloud lane handoff"
cycle: sweep-2026-10-20
repo: damienriehl/FOLIO
status: done — synonym work merged and filed; audit advanced
---

# FOLIO cloud lane — handoff

## Outcome

| Mandate item | Result |
|---|---|
| Triage synonym branches | 4 of 5 were already in `main`. The fifth was rebuilt and merged as **damienriehl/FOLIO#1** (`91b3749`), with 4 terms filed below |
| Resume ontology audit handoff | `automated-ontology-qa` re-verified (181 passed), `main` merged in, 188 passed, pushed (`f9c5152`) |
| IRI minting | Filed as Q3 below. No IRI was minted |

## Evidence

**Branch inventory (verified 2026-10-20 against `main` = `a8f0d29`):**

| Branch | State |
|---|---|
| `add-synonyms-dui`, `add-synonyms-food-public-benefit`, `add-synonyms-patent-registration`, `add-risk-tolerance-capacity` | 0 commits ahead; fully merged |
| `add-synonyms-appellate-appeal` (`bf78c78`) | Superseded by #1 |
| `add-co-investment-fund` (`1d8dd17`) | Head of upstream `alea-institute/FOLIO#16`; still open upstream |
| `docs/change-policy` (`37f49dd`) | 1 ahead. `automated-ontology-qa` carries a later, edited copy of both docs |
| `fix/tribal-language-branch-conflict` (`717aa8a`) | 1 ahead. Gated on `q4-tsimshian-exception` (2026-08-06 handoff) |
| `claude/setup-deployment-platform-7LfvN` | 1 ahead, 13 behind. Railway configs; outside this mandate |

**PR #1** (merged; CI `Tests` and `WebProtégé Merge` green on `main` at `91b3749`):
- Adds `skos:hiddenLabel` Accord(s), Pact(s), Compact(s) to Agreements / Contracts (`R88D8i8AcSTUig2X3yPbFHg`). Ground-triple diff: +6/−0. No label collision with any other concept.
- Fixes `scripts/generate_webprotege_merge.py`, which silently dropped new `hiddenLabel`s on existing classes. Before the fix, none of the 16 original synonyms would have reached the WebProtégé output.
- Adds `tests/test_webprotege_label_additions.py` (7 tests) and `.github/workflows/tests.yml`. Before this, CI ran no tests on `main`.
- A code-review pass found 9 items. I fixed the alt↔hidden S13 overlap, inline close tags, dead code, the missing CI test step, and dropped two terms. The PR body records the rest.

**Audit branch** `automated-ontology-qa`: 181 passed before any change. After merging `main` (one conflict in `compute_semantic_diff`, resolved to keep both sides' intent) it gives 188 passed, and the merge pipeline reports 0 pending changes with byte-identical output. `STATUS-ONTOLOGY-QA.md` carries a 2026-10-20 entry.

## Open questions for Damien

**Q1 — Concordat(s) and Undertaking(s)** · setting: quick-decision
The 2026-08-05 census rated these T0. Review showed both repeat the `e36f3f8` precision bug: a concordat is a treaty, and `Treaties` sits under Legal Authorities, outside Agreements. "Undertaking" usually names a promise (Obligation) or, in EU law, an enterprise.
*Recommendation:* add `Concordat`/`Concordats` as hidden labels on `Treaties` (`RBW9y6esXubLJl4QMtm0Y70`) and drop Undertaking(s).

**Q2 — Send #1 upstream to `alea-institute/FOLIO`** · setting: quick-decision
The fork's `main` matched upstream `main` before #1. Earlier synonym PRs (#5–#9) landed upstream. This session could not attach `alea-institute/FOLIO`, because two same-name repos can't share a session.
*Recommendation:* open an upstream PR from `damienriehl:main` containing #1's four commits. Mention that it also adds a `Tests` workflow. A fresh cloud session sourced on `alea-institute/FOLIO` can do it.

**Q3 — IRI minting: WebProtégé's own IRIs** · setting: quick-decision
The convention is settled: `R` + base62 of 127 bits, via `folio-python>=0.4.0` and `scripts/mint_iri.py` on `automated-ontology-qa`. It still has two loose ends, and both are yours to decide:
1. 1,992 published concepts carry WebProtégé's raw base64url-uuid4 local names. If editors still create classes in WebProtégé, every such class mints outside the convention, and `tests/test_iri_minting.py` cannot see those IRIs until they come back through the merge. Pick one: (a) all new classes go through `mint_iri.py` first, or (b) accept the WebProtégé family as a second legal convention. *Recommendation:* (a), since §2 makes every drifted IRI permanent. I have not verified whether WebProtégé is still used for new classes.
2. `mint_iri.py` and the convention doc exist only on `automated-ontology-qa`, which has never been PR'd upstream. *Recommendation:* land them upstream as their own small PR, separate from the unpublished Release A work.

**Q4 — Stale branches** · setting: quick-decision
I deleted nothing. The four fully-merged branches in the table above carry no commits outside `main`. `add-synonyms-appellate-appeal`'s only unique commit, `bf78c78`, is superseded by #1.
*Recommendation:* delete all five. If you want `bf78c78` kept, tag it first.

**Still open from the 2026-08-06 handoff (not re-asked):** `q1`–`q6` on the Cockpit ask `generative-folio-2026-07-29-audit-fallout`. Check `briefs/qa-state.json` in the cockpit repo. This sweep answers `q7` with Q1 above.

## Box-only steps

- None from this lane. The Release A canary (`NEXT-ONTOLOGY-QA.md`, P1) still needs an `ontology-qa` environment and provider API keys on the fork. Those are credentials and spend, so the canary stays blocked on Damien.

## Not done, by design

- `alea-institute/FOLIO#16` (Co-Investment Fund) is waiting on a maintainer's review. A nudge would go out in Damien's voice, so I did not send one.
- OntoKit indexes no `skos:hiddenLabel` (census §4), so the 6 new labels and the 5,117 existing ones do not show up in FOLIO's viewer search. The fix is a one-line change in `ontokit-api`, which is a different repo.
