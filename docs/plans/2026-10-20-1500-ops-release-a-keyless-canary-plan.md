---
title: "ops: Release A keyless partial canary on the damienriehl/FOLIO fork"
type: ops
status: completed
date: 2026-10-20
origin: cockpit decision folio-2026-10-03-2114-release-a-canary-and-folio16 / canary-setup
---

# Release A keyless partial canary

## Decision

On 2026-10-20, the cockpit decision `canary-setup` chose the keyless partial canary:
put the QA workflows on fork `main`, then prove the deterministic job and the trigger
dispatch. It allows no secrets and no model spend. The full canary, with provider keys,
stays a later credential and spend decision.

## Steps

1. Open a fork PR `automated-ontology-qa` -> `main`. Wait for `Tests` to pass, then merge
   it with a merge commit. `workflow_run` and `workflow_dispatch` fire only from the
   default branch, so fork `main` has to carry both QA workflows.
2. Create the `ontology-qa` environment with a required reviewer. If the environment
   is missing, GitHub creates it with no protection the first time a job references
   it. With the gate in place, the dispatched model-bearing job stops at
   "waiting" before it reads any secret or runs a step.
3. Open a canary PR that makes a no-op change to `FOLIO.owl` (an XML comment).
   - **Expect:** `Ontology Hydration QA` / `deterministic-pr` passes and uploads
     `ontology-deterministic-<sha>`.
   - **Expect:** `Ontology Hydration QA - Automatic Trusted Trigger` resolves the PR
     endpoints and dispatches `ontology-hydration-qa.yml` on `main`.
   - **Expect:** the dispatched run's `trusted-model-review` job waits on the
     `ontology-qa` environment.
4. Cancel the waiting run without approving it. Close the canary PR unmerged and
   delete its branch.
5. Record the run IDs in `STATUS-ONTOLOGY-QA.md` and `NEXT-ONTOLOGY-QA.md`.

## Out of scope

- Provider keys, environment secrets, and any model call: these belong to the full
  canary, which needs its own decision.
- Any PR against `alea-institute/FOLIO`.
- The FOLIO#16 nudge, retired in favour of `folio-2026-10-20-1422-pr15-nudge-canary`.

## Rollback

Revert the merge commit on fork `main`, then delete the `ontology-qa` environment.

## Outcome (2026-10-20)

The keyless canary passed on its fourth attempt. The first three attempts each
surfaced a trigger bug that the stubbed tests could not see.

- **Workflows on main:** fork PR #2 merged `automated-ontology-qa` (merge `a2b5ca6`).
  It also added `jsonschema` to `scripts/requirements.txt` (`8d567fb`), because the
  `Tests` workflow failed collection without it.
- **Gated environment:** `ontology-qa` requires `damienriehl` as reviewer, deploys
  from `main` only, and holds 0 secrets.
- **Trigger bug 1 (PR #4):** the trigger called `actions/runs/{id}/pull_requests`,
  which GitHub does not serve (404). It now reads `.pull_requests` from the run object.
- **Trigger bug 2 (PR #5):** gh rejects `--paginate --slurp` combined with `--jq`. The
  `FOLIO.owl` check now selects matches page by page.
- **Trigger bug 3 (PR #6):** `gh workflow run` had no `--repo` in a job with no
  checkout. It now names the repository.
- **Final run:** deterministic run `39489387823` passed and uploaded
  `ontology-deterministic-83a6415…`. Trigger run `39492121465` succeeded and dispatched
  `39492136725` on `main`. Its `trusted-model-review` job waited on `ontology-qa`, then
  was cancelled without approval after running 0 steps.
- **Cleanup:** canary PR #3 is closed unmerged, and its branch is deleted. The commit
  survives at `refs/pull/3/head`.

### Residual

`WebProtégé Merge` now fails closed on fork `main` (run `39489091541`). It requires a
signed `ontology-qa` attestation for the `FOLIO.owl` hash, and only a full,
model-bearing trusted run can produce one. It stays red on `FOLIO.owl` pushes to
`main` until the full canary runs.
