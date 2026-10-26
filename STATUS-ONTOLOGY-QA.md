# Automated Ontology QA — Status

STATE: Release A keyless canary complete; full canary open. foli-2 plan prepared; live Release B qualification remains blocked.

Last updated: 2026-10-26

## 2026-10-26 — foli-2 qualification plan

- Repository: `folio`; branch: `drawdown/foli-2`. Planning baseline: `417a5e2ece96b011d4209986aa8a5a454c521cca`, clean working tree and no configured remotes.
- Plan: `docs/plans/2026-10-26-1320-fix-release-b-provider-qualification-plan.md`. Scope is Release B qualification correctness and its evidence consumers; the full Release A Actions canary remains `foli-1`, and a general offline readiness reporter remains `foli-4`.
- Static inspection found correction-answer leakage, proposer repeat scoring that ignores replacement text, recall that credits abstentions, a Google fallback that supplies missing served identity, and correction qualification metrics that are not recomputed during replay. The plan assigns focused fixes and offline regression tests; none is implemented in this stage.
- Plan review covered coherence, feasibility, scope, provider trust, and adversarial checks. One finding was resolved by specifying retained blind-request/receipt bindings and a legacy-evidence regression; no review findings remain. The confidence and document checks passed. Automatic cross-model review is disabled by checkout configuration; the campaign's Astra and Fable reviews remain controller-owned prerequisites.
- Re-verification was source inspection only. No tests, provider calls, credentials, spend, workflow dispatches, or remote publication occurred. Historical results below retain their original dates and are not a fresh passing baseline.
- Genuine provider availability and qualification remain unverified. Current model pins are configuration; the historical model/cost proposal was not adopted. Neutral numeric controls do not establish broad legal-language competence.
- The chief campaign source and Cockpit scanner are absent from this sandbox. The lane's supplied campaign rules were preserved; the controller must reconcile the Goal Capsule and cited R-IDs and verify scanner attribution to `folio`. Matching top-level filenames is not evidence that the scanner ran.
- Live provider access, bounded spend, and existing trusted-environment approval remain external prerequisites. The local build can proceed independently after controller handoff; Release B must stay open until genuine evidence satisfies the plan.

## Release A outcome

Release A is implemented on branch `automated-ontology-qa`.

- Changed-record corrections now run through the trusted QA runner.
- Correction outputs are staged and atomically published as one directory.
- Corrected ontologies receive deterministic final validation and dual-provider rereview.
- Fresh-SHA workflow handoff preserves and restores correction lineage.
- Automatic triggers recover the correction artifact and dispatch the corrected SHA.
- Offline replay loads review policy, honors correction lineage, and rejects tampered evidence.
- Workflow guards cover provenance, structured contracts, correction success/failure, and fresh-SHA replay.

## Verification

- Full suite: `128 passed in 13.70s`.
- Python compilation, workflow YAML parsing, and `git diff --check` passed.
- Production-shaped replay and tamper matrices passed.
- Independent-provider behavior is integration-tested with stubs; no live model calls were made.

## Commits

- `f20c0b4` — `feat(ontology): complete automated correction handoff`
- `928364e` — `docs(ontology): record Release A follow-ups`

## Constraints and residuals

- Release B depends on genuine cross-provider availability.
- Do not use Claude before Saturday morning, America/Chicago.
- Do not repeatedly retry OpenAI while the account has no credits.
- The trusted-runner extraction residual is done (2026-10-03); the real GitHub Actions canary remains open.
- Detailed residual findings live in `docs/residual-review-findings/automated-ontology-qa.md`.
- `automated-ontology-qa` is pushed to `origin` (the `damienriehl/FOLIO` fork); no pull request has been opened against `alea-institute/FOLIO`.
- User-owned untracked files remain preserved.

## 2026-08-17 — Co-Investment Fund and IRI minting

- Added the `Co-Investment Fund` class (`R1cNH7TLMiSlSbIbdFsynUk`) under `Investment Funds`; commit `94e0e83`.
- Opened focused [alea-institute/FOLIO#16](https://github.com/alea-institute/FOLIO/pull/16) from a clean branch off `upstream/main`; it contains only the class (`FOLIO.owl`, +29/−0). The PR remains open and mergeable with no comments or reviews; Mike Bommarito's review was requested on 2026-08-17.
- Added `scripts/mint_iri.py`, which carries no generation logic and imports `folio.iri` from folio-python so there is one implementation; commit `f8dd90c`.
- Filed [alea-institute/folio-python#19](https://github.com/alea-institute/folio-python/pull/19), which moves the generator to `R` + base62, fixes a uniqueness check that could never fire, and removes a path that emitted local names shorter than the library's own assertion allows.
- `alea-institute/folio-python#19` remains open and mergeable with no comments or reviews; Mike Bommarito's review is requested and all six architecture checks pass.
- `folio-python>=0.4.0,<0.5.0` now lives in `scripts/requirements.txt`: alea-institute/folio-python#19 merged and shipped as 0.4.0 on PyPI (verified 2026-10-03), so `tests/test_iri_minting.py` gates CI instead of skipping.
- Regenerated `FOLIO-webprotege-merge-output.owl`; commit `db354e1`.
- Fixed a pre-existing silent no-op in `scripts/generate_webprotege_merge.py`: definition updates on attributed `<skos:definition>` tags were detected, never applied, and still counted as applied. The fix propagated one pending definition (`R5RoVVyRmkyMepjXK7X1sp`, No-Fault Claim); the India-specific term it dropped from the prose is already modelled structurally as `v1:country`, so nothing was lost.

## 2026-10-03 — Residual cleanups

- `5b935e8` extracts the changed-record correction stage into `scripts/ontology_qa/changed_record_corrections.py` and shares the response-set and write-once helpers with the confirmed-defect runner via `scripts/ontology_qa/correction_artifacts.py`. Pure move; `run_trusted_ontology_qa.py` is 1,011 lines (was 1,200).
- `e72dd7c` normalises `xsd:string` literals against plain ones in `compute_semantic_diff`. Against the committed files, the merge run now reports 0 changes (was a phantom No-Fault Claim update) and 90 other removals (was 93; the 3 dropped were `xsd:string` noise on Billable Hour, Flat Fee, and No-Fault Claim). Output is byte-identical.
- Full suite: 181 passed, 0 skipped.
- The canary is blocked on credentials and spend; see `NEXT-ONTOLOGY-QA.md`.

## 2026-10-20 — Sweep re-verification and main merge

- Re-ran the suite on `7b4637f` before touching anything: 181 passed.
- `damienriehl/FOLIO#1` merged to `main`: six Agreements `skos:hiddenLabel`s (Accord(s), Pact(s), Compact(s)) and a merge-pipeline fix — new `hiddenLabel`s on existing classes were never propagated to the WebProtégé output. This resolves `q7-agreements-terms` from the 2026-08-06 handoff for 6 terms; `Concordat(s)` and `Undertaking(s)` were held back (see the sweep handoff).
- Merged `main` into this branch. One conflict in `compute_semantic_diff`: kept this branch's `_norm_literal` comparison and `main`'s narrower removal suppression; hidden-label detection now normalises like alt-label detection.
- Full suite after the merge: 188 passed. Merge pipeline on the committed files: 0 pending changes, byte-identical output.

## 2026-10-20 — Keyless partial canary

- Cockpit decision `canary-setup` chose the keyless partial canary. Plan and full
  receipt: `docs/plans/2026-10-20-1500-ops-release-a-keyless-canary-plan.md`.
- Fork `main` now carries the QA workflows (fork PR #2). The `ontology-qa`
  environment needs `damienriehl`'s approval, deploys from `main` only, and holds no
  secrets.
- The canary found and fixed three trigger bugs: a nonexistent REST endpoint (#4),
  `--slurp` combined with `--jq` (#5), and a missing `--repo` (#6). After the fixes, the
  deterministic job passed and the trigger dispatched the trusted run, which stopped
  at the environment gate. That run was cancelled unapproved, after 0 steps.
- Full suite: 191 passed.
- `WebProtégé Merge` on fork `main` fails closed until a full canary produces an
  attestation.
