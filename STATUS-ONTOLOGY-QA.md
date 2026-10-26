# Automated Ontology QA — Status

STATE: foli-1 local build reviewed and committed; full-size manifest preflight and live canary unverified

Last updated: 2026-10-26

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

## 2026-10-26 — foli-1 planning checkpoint

- Reverified the local starting tree at `417a5e2` on `drawdown/foli-1`: clean checkout, no configured remote. The mandate's missing-workflows description is superseded by the October 20 keyless-canary receipt; current remote state was not inspected.
- Scoped plan: `docs/plans/2026-10-26-1224-fix-foli-1-actions-canary-plan.md`. It covers executable correction-handoff tests, final PR endpoint checks, and the real U7/U10 canary procedure. It preserves the existing approval-assisted workflow chain and excludes provider-policy changes and the separate offline-readiness expansion.
- Source inspection found that the final acceptance fence checks commit existence and ontology/report hashes without rechecking the live PR head, base, and repository. The plan requires rejection of observed stale endpoints before acceptance publication.
- Planning only: no implementation, tests, provider calls, GitHub mutations, credential access, or security-setting changes occurred. The 191-test result above remains historical evidence.
- Plan review covered coherence, feasibility, scope, security, and adversarial checks. One prerequisite-summary contradiction was corrected: the controller authority check precedes local build; provider access, budget, and approvals hold the live phase. No review findings remain open.
- Full canary execution still requires authorized provider access and spend, existing required Actions approvals, and actual successful correction, acceptance, replay, and WebProtégé fidelity evidence. Local verification cannot close that live milestone.
- The chief campaign plan and Cockpit scanner are unavailable in this sandbox. The controller must verify the campaign Goal Capsule and cited requirements before build, then confirm scanner attribution to repository ID `folio`. Top-level state/action formatting is not a substitute for that scan.

## 2026-10-26 — foli-1 build checkpoint (U1)

- Started from clean plan commit `dc23f1c` on `drawdown/foli-1`. The controller's build instruction authorizes the local U1–U3 work under the supplied campaign rules; the chief excerpts remain unavailable for independent verification.
- Installed declared test dependencies in a disposable environment after the system interpreter lacked them. Reverified the unchanged baseline: 191 passed in 14.96s.
- Added executable Bash coverage with a closed command boundary for artifact discovery, paginated file detection, exact dispatch inputs, provenance/byte rejection, restoration arguments, and correction failure-before-push ordering. New and existing workflow tests: 27 passed in 1.12s.
- No live workflow, provider, registry, credential, or security-setting operation occurred. U2 endpoint checks and U3 canary preparation remain in progress; U4 remains outside this sandbox's authority.

## 2026-10-26 — foli-1 endpoint checks (U2)

- Added fresh PR head/base/repository checks before evidence publication, immediately before signing, and before successful stable-check publication. Unavailable, empty, malformed, missing, or changed metadata rejects acceptance. The always-run final step attempts a negative check after earlier failures and fails when publishing the check fails.
- Restoration now requires all four nonempty lineage files before model execution. Existing candidate hash, provenance, source-SHA binding, correction guards, and token permissions are preserved.
- Proof first: 28 new regressions failed against the original workflow (including three missing-file paths and absent endpoint fences); fixes passed the focused 84-test suite. Three additional empty-response cases also pass. Final full suite: 235 passed in 17.30s.
- Integration review caught that adding endpoint observations to the indexed bundle would invalidate replay. A regression demonstrated that failure; diagnostics now live outside the immutable evidence directory and remain in the bounded failure upload.
- All four workflow YAML files and their Bash blocks parse; `git diff --check` passes. Independent API observations cannot make acceptance atomic with PR mutation; already signed immutable evidence is not revoked if movement is observed afterward.

## 2026-10-26 — foli-1 canary preparation (U3; U4 still open)

- Added `docs/ontology-qa-release-a-canary.md`: exact existing-class mutation, input/record hashes, current-chain approval points, source/fresh lineage checks, attestation/replay and consumer evidence, bounded attempts, and required receipt fields. No ontology or generated output changed in the branch.
- Disposable Billable Hour fixture: full census inspected 106,271 annotations and passed baseline-relative validation with zero new failures, 199 inherited failures, and 68 semantic-review risks. SHACL remains false because of inherited debt. Full parsed annotation-set comparison found exactly one removed and one added definition; class-scoped existing delta generation confirmed the recorded identity.
- The committed WebProtégé base has the exact baseline literal and metadata. The existing merge pipeline applied one definition update and passed XML/RDF validation; the resulting bytes equal that base with only the intended definition substituted. This is preparation evidence, not provider acceptance or the real consumer receipt.
- Full-size canonical manifest generation remains unverified. It did not return within 15 minutes on the 172,062-triple ontology and was stopped with inputs preserved; its runtime preflight remains open before a live dispatch. No delta algorithm, policy, or coverage limit was changed to obtain a result.
- Local-only lane: no push, PR, deployment, provider call, registry write, credential access, or security-setting change. Provider access/budget and existing reviewer gates still hold U4. Chief campaign excerpts and real Cockpit attribution require controller verification; local file formatting is not scanner evidence.

## 2026-10-26 — foli-1 review and local delivery

- Simplification reviewed reuse, quality, efficiency, tests, and comments; no code changes were warranted. Proof tests were preserved. No standalone lint/typecheck configuration exists; verification used pytest, YAML parsing, Bash syntax checks, and diff checks.
- Full code review (`20261026-foli1-final`) completed correctness, adversarial, testing, security, maintainability, reliability, standards, and documented-learning checks. No code findings. The one P2 documentation finding was independently reproduced: restoring exact B bytes removes `FOLIO.owl` from the PR delta, so the trigger skips fresh dispatch. The runbook now stops that attempt as incomplete and retains its evidence.
- Review correction is documentation-only; targeted trigger/correction checks passed. The final implementation suite remains 235 passing tests, including 44 new execution tests; every pre-existing test and both published ontology files remain unchanged.
- Browser verification: no affected frontend files or routes; no screenshot applies. No new service, migration, data rewrite, package release, or deployment configuration was introduced.
- U1–U3 local deliverables are ready for controller publication. U4 remains unverified, including full-size manifest runtime, real provider/Actions evidence, and accepted WebProtégé fidelity. These are not replaced by the local tests or preparation checks.
