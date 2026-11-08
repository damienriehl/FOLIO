---
title: A self-merging heartbeat needs its own test gate, and a TSV contract needs one dialect
date: 2026-11-08
category: integration-issues
module: opengloss-mapping
problem_type: integration_issue
component: tooling
severity: medium
applies_when:
  - A scheduled workflow opens or merges its own pull request
  - A generated TSV file is read by code in another repository
tags: [github-actions, github-token, auto-merge, sssom, tsv, csv, quoting, heartbeat]
---

# A self-merging heartbeat needs its own test gate, and a TSV contract needs one dialect

## Context

The OpenGloss mapping heartbeat (`.github/workflows/opengloss-mapping-heartbeat.yml`)
regenerates `mappings/opengloss/` when an upstream moves, then opens and merges its own pull
request. Code review of its first draft found two defects that every test passed over.

## Problem 1: nothing gates a pull request opened by `GITHUB_TOKEN`

A pull request that a workflow opens with `GITHUB_TOKEN` does not start any other workflow,
`pull_request` workflows included. So `Tests` never runs on a heartbeat pull request.

The first draft asked for `gh pr merge --auto`, which fails in two ways:
- **No protection:** `main` had no branch protection, so with no pending required checks the
  request errored out, and `|| echo` swallowed the error.
- **Required checks:** had `main` required checks, they would never report on a bot pull
  request, and auto-merge would wait forever.

**Fix:**
- **Gate:** run the test suite inside the heartbeat job and treat that run as the merge gate.
- **Merge:** merge `auto` decisions directly with `gh pr merge --squash`, and fail the job loudly
  if the merge fails.
- **Test failure:** a failed test run forces the `needs-damien` label, and the pull request still
  publishes so the receipt survives.
- **Branch names:** make each run's branch unique, so a rerun cannot collide.
- **One at a time:** skip the run while another heartbeat pull request is open, so two runs never
  race on the same set version.
- **Failed runs:** a failed run commits only its receipt, never the mapping files or pins. That way
  the next run rebuilds from a clean base.

A `workflow_dispatch` canary on `main` proved the check path live. Stubbed tests had not.

## Problem 2: writer and readers used different TSV dialects

The writer used `csv`'s default `QUOTE_MINIMAL`. The validator, scorer and exporter read with
`QUOTE_NONE`, and the consumer (folio-resolve) read with the default.

76 FOLIO labels contain a literal `"`, which became RFC 4180 quoting in the file. So the
in-repo readers kept the doubled quote characters, and a consumer reading with `QUOTE_NONE`
would have kept them too.

**Fix:** pick one dialect and state it in the contract. Every file here is tab-separated with
`QUOTE_NONE`. The writer strips tabs and newlines, so no escaping is ever needed, and it fails
loudly if a delimiter survives. A round-trip test pushes a quote-bearing label and gloss through
the writer, the validator and the exporter. The README tells consumers to parse with
`quoting=csv.QUOTE_NONE`.

## Prevention

- **Gate bot pull requests:** for any workflow that opens a pull request with `GITHUB_TOKEN`,
  assume no other workflow runs on it, and gate the merge inside the same job.
- **Assert the guard:** test that the merge call sits behind its decision guard, not just that the
  merge command appears.
- **Pin the dialect:** for any TSV or CSV that crosses a repository boundary, write the quoting
  rule into the contract, and test a round trip with the characters that trigger quoting.
