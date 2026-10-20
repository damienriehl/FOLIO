---
title: Keyless canary exposed three gh and API bugs that the stubbed workflow tests missed
date: 2026-10-20
category: integration-issues
module: ontology-qa-workflows
problem_type: integration_issue
component: infrastructure
symptoms:
  - "Trigger step failed with gh: Not Found (HTTP 404) on actions/runs/{id}/pull_requests"
  - "gh printed: the `--slurp` option is not supported with `--jq` or `--template`"
  - "gh workflow run failed with: failed to run git: fatal: not a git repository"
root_cause: wrong_api
resolution_type: code_fix
severity: high
related_components:
  - testing_framework
tags: [github-actions, workflow-run, workflow-dispatch, gh-cli, canary, environments, ontology-qa]
---

# Keyless canary exposed three gh and API bugs that the stubbed workflow tests missed

## Problem

The Release A ontology QA chain runs in three hops. A `pull_request` check runs
first. A `workflow_run` trigger follows it, and that trigger issues a
`workflow_dispatch` for the secret-bearing trusted job. The chain carried 188
passing tests, yet no part of it had ever run on GitHub. The tests assert on
workflow text (`tests/test_workflow_contract.py`) and stub the provider calls,
so none of them executes a `gh` command against the real API. On its first live
run, the trigger failed three times in a row, a different bug each time.

## Symptoms

- **Bug 1:** `gh: Not Found (HTTP 404)` from
  `gh api repos/$GITHUB_REPOSITORY/actions/runs/$RUN_ID/pull_requests`.
- **Bug 2:** `` the `--slurp` option is not supported with `--jq` or `--template` ``
  from `gh api --paginate --slurp ... --jq 'any(.[][]; ...)'`.
- **Bug 3:** `failed to run git: fatal: not a git repository` from
  `gh workflow run ontology-hydration-qa.yml ...`.

## What Didn't Work

- **Stubbed contract tests:** these assert that strings such as
  `gh workflow run ontology-hydration-qa.yml` appear in the YAML. They prove the
  wiring is spelled as intended, not that GitHub serves the endpoint or that gh
  accepts the flags. All three bugs passed them.
- **Switching the fork's default branch** to the QA branch so the triggers would
  fire. The auto-mode permission classifier denied that on 2026-10-05, per the
  branch handoff `docs/handoffs/2026-10-20-release-a-canary-and-qa-residuals.md`.
  The approach that worked merged the QA branch into the default branch (fork PR #2)
  instead.

## Solution

Fork PRs #4, #5, and #6 fix the three bugs in
`.github/workflows/ontology-hydration-qa-trigger.yml`, each with a contract test:

```bash
# 1. The run object already carries pull_requests[] (trigger.yml:26)
- gh api "repos/$GITHUB_REPOSITORY/actions/runs/$RUN_ID/pull_requests" --jq '.[0].number'
+ gh api "repos/$GITHUB_REPOSITORY/actions/runs/$RUN_ID" --jq '.pull_requests[0].number // empty'

# 2. --paginate applies --jq per page, so select per page (trigger.yml:30-32)
- gh api --paginate --slurp ".../pulls/$PR_NUMBER/files" --jq 'any(.[][]; .filename == "FOLIO.owl")'
+ FOLIO_FILES="$(gh api --paginate ".../pulls/$PR_NUMBER/files" --jq '.[] | select(.filename == "FOLIO.owl") | .filename')"
+ ONTOLOGY_CHANGED=false; if [ -n "$FOLIO_FILES" ]; then ONTOLOGY_CHANGED=true; fi

# 3. The job has no checkout, so gh cannot infer the repo (trigger.yml:68)
  gh workflow run ontology-hydration-qa.yml \
+   --repo "$GITHUB_REPOSITORY" \
```

### The keyless canary technique

The canary proves the chain without secrets or model spend:

1. **Default branch:** put the workflows on it. `workflow_run` and `workflow_dispatch`
   run only the default branch's copy of a workflow.
2. **Gated environment:** before the first dispatch, create the environment the
   trusted job names (`environment: ontology-qa`, `ontology-hydration-qa.yml:82`)
   with a required reviewer and a `main`-only branch policy. A job that references a
   missing environment makes GitHub create it with **no** protection, which would
   leave the job free to run.
3. **Canary PR:** touch the watched file with a census-clean change.
4. **Assert the gate:** the dispatched run must show `waiting`, and
   `GET .../actions/runs/{id}/pending_deployments` must name the environment. Cancel
   the run unapproved. Its job lists 0 steps, which proves no secret was read.
5. **Retest by rerun:** after each trigger fix merges, run
   `gh run rerun <pull_request check run id>`. Completing that check fires
   `workflow_run` again against the **current** default-branch trigger, so a fix
   gets retested without a new canary commit.

Evidence: deterministic run `39489387823`, trigger run `39492121465`, and
dispatched run `39492136725` (waited, then cancelled after 0 steps). See
`docs/plans/2026-10-20-1500-ops-release-a-keyless-canary-plan.md`.

## Why This Works

All three bugs live where the workflow meets GitHub's real surface:

- **Bug 1:** an endpoint shape that GitHub does not serve.
- **Bug 2:** a gh flag combination that gh refuses.
- **Bug 3:** gh's habit of inferring the repository from a git checkout that this
  job never made.

Text assertions cannot see any of them, and a live run catches all three. The gated
environment turns the most dangerous hop, the secret-bearing job, into a passive
probe. The job gets as far as the deployment gate, which shows that the dispatch
landed, and stops before any step runs.

## Prevention

- **Name the repo:** in any job without `actions/checkout`, pass
  `--repo "$GITHUB_REPOSITORY"` to repo-scoped gh subcommands (`gh workflow`,
  `gh run`, `gh pr`, `gh release`). `gh api` takes the repository in its path and
  needs no flag. `test_trigger_dispatch_names_repository` guards this.
- **Never combine `--slurp` with `--jq`:** filter per page instead.
  `test_trigger_never_combines_slurp_with_jq` guards this.
- **Verify endpoints locally:** before a workflow relies on a REST path, run it once
  with `gh api` against a real run. Bug 1 reproduces in one command.
- **Gate before dispatch:** create a required-reviewer gate for every environment a
  secret-bearing job names, before anything can dispatch that job.
- **Canary new triggers:** run a keyless canary for any new `workflow_run` or
  `workflow_dispatch` chain before you count it as releasable. Passing contract tests
  do not establish that it runs.
