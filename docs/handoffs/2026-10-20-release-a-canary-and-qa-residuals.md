# Handoff — Release A canary, QA residuals, and FOLIO#16

_Written 2026-10-20 on branch `automated-ontology-qa`._

## Done in this session (2026-10-03)

- `a415d85` — `folio-python>=0.4.0,<0.5.0` moved into `scripts/requirements.txt`
  (alea-institute/folio-python#19 shipped as 0.4.0), so `tests/test_iri_minting.py`
  gates CI.
- `5b935e8` — changed-record correction stage extracted from
  `scripts/run_trusted_ontology_qa.py` (1,200 → 1,011 lines). Pure move.
- `e72dd7c` — `xsd:string` literals compare equal to plain ones in the WebProtégé
  merge diff. Merge output byte-identical; phantom No-Fault Claim update gone.
- Suite at that point: 181 passed, 0 skipped.

## Open

1. **Release A canary (keyless partial) — DONE 2026-10-20.** The fork's `main` now
   carries the QA workflows (fork PR #2), with no default-branch switch. The
   canary proved the deterministic job, the trigger, and the dispatch. The
   dispatched trusted job waited on the gated `ontology-qa` environment and was
   cancelled unapproved. Three trigger bugs were fixed in fork PRs #4 to #6.
   Receipt: `docs/plans/2026-10-20-1500-ops-release-a-keyless-canary-plan.md`.
   Learning: `docs/solutions/integration-issues/keyless-canary-for-workflow-run-dispatch-chain.md`.
   The prepared altLabel change in the old `canary/release-a-keyless` worktree is
   superseded (the same edit ran as fork PR #3).
2. **Full canary** needs an OpenAI Platform key and a Gemini key in the fork's
   `ontology-qa` environment (spend + credential gate; Codex credits do not
   apply). Proposed model change: `gpt-6-luna` for primary and correction
   proposer, `gpt-6-sol` for benchmark adjudicator and verifier 2 — the
   `provider:model` route-separation rule in `scripts/ontology_qa/qualification.py`
   forbids one OpenAI model in all four roles. Estimated canary cost about $10
   proposed vs $23 today (qualification dominates; it re-runs every trusted run).
3. **FOLIO#16** — still open, 0 reviews, 0 comments as of 2026-10-20. Nudge
   question moved to `folio-2026-10-20-1422-pr15-nudge-canary`.

## Things that will bite you

- The census exits 0 when nothing regresses against the baseline; the 199 legacy
  failures sit in the baseline. A clean canary PR can therefore turn the
  deterministic check green, which the trigger requires.
- `webprotege-merge.yml` now runs on the fork's `main` and **fails closed** on every
  `FOLIO.owl` push until a full canary produces a signed `ontology-qa` attestation.
  That failure is expected, not a regression.
- The `ontology-qa` environment requires `damienriehl` as reviewer and holds no
  secrets. The full canary means adding both keys as environment secrets, then
  approving the waiting deployment.
