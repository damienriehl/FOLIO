---
title: "FOLIO enrichment write-back — audit findings and open decisions"
status: handoff
created: 2026-08-06
audience: "next session, any harness — assume no prior context"
---

# FOLIO enrichment write-back — handoff

For a Codex session that has never seen this repo: read this before touching
`FOLIO.owl`, `docs/writeback/`, or `docs/FOLIO-CHANGE-POLICY.md`.

## What this covers

A generation pipeline in the sibling `generative-folio` repo proposed 151,078
additions (definitions, examples, translations) to the FOLIO legal ontology,
staged as `docs/writeback/digest-0001/` there. It is held at a human gate —
nothing has been written to `FOLIO.owl` from it. This handoff is about the audit
of that proposal and the decisions it produced, not about implementing anything.

## What was tried and abandoned

**Trusting the locale pre-screen as a quality signal — wrong, don't repeat it.**
The `generative-folio` gf1 locale gate reported 0.10–0.22% flag rates on
he-il/hi-in/ja-jp/zh-cn and was treated, at first, as evidence those locales were
fine. A seeded audit later found 26–60% real defect rates in the same locales.
**The gate tests well-formedness (wrong script, malformed XML), not semantic or
legal correctness — a passing gate is not evidence of accuracy.** Any future
quality gate needs a semantic check, not just a format check.

**The tribal/language taxonomy fix's original reasoning — abandoned.** A prior
proposal (`docs/writeback/tribal-fix/PROPOSAL.md` in `generative-folio`, applied
on this repo's `fix/tribal-language-branch-conflict` branch) argued 14 concepts
(Cherokee, Choctaw, Mohawk, etc.) were languages rather than tribes *because their
own `skos:definition` said so*. That reasoning is circular: the same generation
pipeline was later shown to hallucinate definitions in exactly this area (inventing
federal tribal recognition — see below). **Do not use a concept's own generated
definition as evidence of what kind of thing it is.** Use ontology structure
instead — the corrected approach checked whether FOLIO already contains a
*distinct* tribal-entity concept for each people (it does, for 13 of 14; not for
Tsimshian — see Open Decisions).

## Decisions made in conversation, not yet in any commit

- Damien holds the corpus is not fit to write in its current form (32% observed
  defect rate on a seeded audit). Not encoded anywhere except the Cockpit ask below.
- He specifically distrusts generated content that asserts legal/governmental
  status without a sourced basis — the tribal-recognition hallucination is the
  concrete trigger, but the principle is broader than that one template.
- He wants a review/correction surface built in `ontokit-web`, not in this repo
  or in `generative-folio`. Requirements were written for that handoff:
  `generative-folio/docs/handoffs/2026-07-28-ontokit-diff-viewer-requirements.md`.
  That document has not yet been fed into a `ce-brainstorm` session.

## Where this stops — precisely

Seven questions are open on a Cockpit ask (repo: `generative-folio`, stem
`generative-folio-2026-07-29-audit-fallout`, severity `blocking`). **Nothing
downstream should proceed past what's already been decided until these are
answered.** Summary (full text and options are in the ask JSON, not duplicated
here — do not let it drift out of sync):

| qid | What's undecided |
|---|---|
| `q1-digest-disposition` | Salvage vs. full regen vs. narrow-scope vs. park the 151K-row digest |
| `q2-en-gb-drop` | Whether to drop ~3,691 verbatim-duplicate en-gb rows from the proposal |
| `q3-tribal-recognition-gate` | How to gate the 481 hallucinated-recognition definitions before any future regen |
| `q4-tsimshian-exception` | Tsimshian has no distinct tribal entity in FOLIO — split into twins, leave alone, or revert the whole 14-concept fix |
| `q5-network-verification` | Two verifications (BIA tribal list, ISO 639-2 list) need network access no sandboxed worker in this environment has |
| `q6-live-corrections` | The **already-published** FOLIO.owl has its own defects (10% definitions, 26.7% translations, 89.6% of en-gb alt-labels are duplicate copies) — separate from the unwritten digest, and how to fix them |
| `q7-agreements-terms` | A reviewed-but-unmerged branch adds 16 hidden-label synonyms to Agreements; review recommends merging only 10 |

Check `briefs/qa-state.json` (cockpit repo) before re-asking any of these —
Damien may have answered since this was written.

## What you'd want to know that the code won't tell you

- **The published `FOLIO.owl` enrichment (15,662 definitions, 2,868 examples,
  52,238 translations) did NOT come from the `generative-folio` pipeline.** It
  predates it — present already in the original SOLI-era commit before the
  project was renamed to FOLIO. Don't assume the two share a generator or a
  quality profile; they were independently audited and came out differently
  (the live file is cleaner on definitions, worse on `en-gb` duplication).
- **`docs/FOLIO-CHANGE-POLICY.md` and `docs/2026-08-05-staged-change-census.md`
  exist in this repo but were not authored or verified by the session that wrote
  this handoff.** They appear to build on the digest-0001 audit findings (the
  census's totals reconcile closely with digest-0001's 151,078) and look like
  careful, structured follow-on work — but treat that as an unverified
  impression, not a review. If you're picking this up, read those two documents
  yourself before trusting their classifications, and consider running an
  independent adversarial check the same way the digest-0001 audit was run
  (seeded random sample, judged against each concept's own ontology context,
  not against the proposal's own stated reasoning).
- **A locale gate passing is not a quality signal for legal or semantic
  correctness** — see above. If you build or reuse any acceptance gate for this
  content, it needs a semantic check, not just a well-formedness check.
- **The apply path from a digest to actual `FOLIO.owl` commits does not exist
  yet.** `generative-folio/docs/writeback/digest-0001/payload/*.jsonl` is
  row-level data, not patches; only one branch (`Status`) has a real diff, as a
  shape demonstration. `apply_to_owl()` in `generative-folio/scripts/writeback_digest.py`
  is an internal function with no CLI wired to it.

## Unverified — flagged as such, don't treat as fact

- Whether `automated-ontology-qa`'s commits in this repo were produced by an
  automated/Codex pipeline or a different session is not confirmed from inside
  this repo — inferred only from commit message style and timing.
- Whether the `docs/2026-08-05-staged-change-census.md` tiering is *correct*
  (as opposed to internally consistent) has not been independently checked.
- The claim that Tsimshian has zero distinct tribal entities in FOLIO was
  established by one Codex worker's structural search of `FOLIO.owl`, not
  cross-checked against an authoritative external tribal registry (that check
  is exactly what `q5-network-verification` is asking permission to run).

## Authoritative references

- `docs/2026-07-29-published-content-audit.md` (this repo) — the live-file audit.
- `docs/FOLIO-CHANGE-POLICY.md`, `docs/2026-08-05-staged-change-census.md`
  (this repo, unverified — see above).
- `generative-folio/docs/evidence/2026-07-28-writeback-random-sample-audit.md` —
  the digest-0001 audit (32% defect rate).
- `generative-folio/docs/writeback/digest-0001/` — the staged proposal itself.
- `generative-folio/docs/writeback/tribal-fix/PROPOSAL.md` — the original
  (partially superseded) tribal/language fix reasoning.
- `generative-folio/docs/handoffs/2026-07-28-ontokit-diff-viewer-requirements.md` —
  ready for a `ce-brainstorm` handoff in `ontokit-web`.
- Cockpit ask `briefs/qa/generative-folio-2026-07-29-audit-fallout.json` — the
  live decision surface; treat it as more current than this document.

## Plausible next steps

1. Check whether the 7-question ask has been answered; if so, execute the
   chosen path for `q1` (digest disposition) first — it gates most of the rest.
2. Independently audit the `automated-ontology-qa` branch's content before
   building on it or proposing it for merge.
3. If `q4-gfchain-diff-view` (a separate, earlier Cockpit ask,
   `cockpit-2026-07-27-backlog-status-decisions`) has been answered to proceed,
   hand `generative-folio/docs/handoffs/2026-07-28-ontokit-diff-viewer-requirements.md`
   to a `ce-brainstorm` session in `ontokit-web`.
