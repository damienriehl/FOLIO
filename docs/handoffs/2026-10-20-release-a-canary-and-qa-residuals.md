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

1. **Release A canary (keyless partial).** Chief answered `canary-setup` with the
   keyless partial canary (Decision Sheet `folio-2026-10-03-2114-release-a-canary-and-folio16`,
   re-asked in `folio-2026-10-20-1422-pr15-nudge-canary`). The trigger and the
   trusted dispatch only fire from the fork's **default branch**, which is `main`
   and lacks the QA workflows. The setup step (switch the fork's default branch to
   `automated-ontology-qa`, push a canary branch, open a do-not-merge PR in the
   fork) was **denied by the auto-mode permission classifier on 2026-10-05**. Do
   not retry it by another route; it needs Damien's permission rule or direct
   approval. A prepared canary change (one altLabel on Co-Investment Fund,
   census-verified to exit 0 with no regressions) sits uncommitted in a local
   worktree for branch `canary/release-a-keyless`.
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
- `webprotege-merge.yml` runs on pushes to `main` that touch `FOLIO.owl`; merging
  this branch into the fork's `main` would start it.
