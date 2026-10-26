---
title: Release A Actions Canary Closure - Plan
type: fix
date: 2026-10-26
artifact_contract: ce-unified-plan/v1
product_contract_source: drawdown-mandate
execution: code
origin: docs/plans/2026-07-30-001-feat-automated-ontology-qa-plan.md
item: foli-1
kind: planned
---

# Release A Actions Canary Closure - Plan

## Goal Capsule

- **Objective:** Maintainers can verify on GitHub that a corrected ontology receives acceptance on its own commit and that WebProtégé consumes those accepted bytes.
- **Means:** Exercise the existing correction-to-fresh-SHA workflow, strengthen its final endpoint checks, and retain a complete canary receipt (KTD1–KTD3).
- **Scope:** Only mandate item `foli-1`, the remaining Release A U7/U10 canary in the origin plan. This scoped continuation leaves the origin Product Contract and its IDs unchanged; units and R-IDs below are local to this document.
- **Authority:** The campaign plan in the chief repository, `docs/plans/2026-10-26-0705-feat-codex-drawdown-campaign-plan.md`, then the supplied lane rules and this repository's `AGENTS.md` and origin plan. The chief checkout is not available here: its Goal Capsule and cited R11/R15/R16/R17/R19/R20 have not been independently read. The controller must verify those excerpts before build; this plan uses only the rules reproduced in the mandate.
- **Execution:** The current assignment produces and locally commits this plan on `drawdown/foli-1`. Implementation and tests belong to the later build stage. The lane has no remote or GitHub login; the controller owns publication, PR creation, and the campaign merge gate.
- **Stops:** R5 governs credential, spend, security, data, and publication limits. Missing live prerequisites hold only U4; they do not prevent the local U1–U3 work. Local success never establishes live canary completion.

---

## Product Contract

### Summary

Add executable coverage for correction artifact discovery, dispatch, and restoration, then repair the final acceptance checks that currently miss a moving pull request.
Prepare a bounded canary procedure using the existing workflows and record real provider-backed correction, acceptance, and WebProtégé evidence when its external prerequisites are available.

### Problem Frame

The mandate's missing-default-branch-workflow description is stale relative to this checkout.
At `417a5e2`, the October 20 receipt records successful keyless dispatch and three trigger fixes, but the trusted job was cancelled before executing a step.
That result does not prove the correction-to-fresh-SHA path, signing, durable evidence retrieval, or the WebProtégé consumer.
Maintainers still lack the live evidence required to close origin U7/U10.

### Reverified starting state

| Evidence | What it establishes | Limit |
|---|---|---|
| `417a5e2`, clean `drawdown/foli-1`, no configured remote | Local starting tree and branch | No fresh fork/API state was inspected |
| `docs/plans/2026-10-20-1500-ops-release-a-keyless-canary-plan.md` | Recorded deterministic run `39489387823`, trigger `39492121465`, trusted dispatch `39492136725`; workflows merged to fork `main` | Historical receipt; trusted run cancelled unapproved after zero steps |
| `docs/handoffs/2026-10-20-release-a-canary-and-qa-residuals.md` | Full canary still requires provider access and approval | Current account availability is unknown |
| `docs/residual-review-findings/automated-ontology-qa.md`, item 2 | Exact residual is correction artifact discovery and fresh-SHA lineage restoration | Not closed by the keyless canary |
| `.github/workflows/ontology-hydration-qa.yml` | Correction upload precedes correction push; fresh review accepts source-run/source-SHA inputs | Final fence checks commit existence and ontology hash, not live PR head/base/repository |
| `tests/test_workflow_contract.py` | Existing assertions cover workflow text and guards | They do not execute the shell/API boundary |
| `STATUS-ONTOLOGY-QA.md` | Last recorded full suite was 191 passing tests | Historical only; no tests ran during this planning stage |

### Requirements

**Correction and acceptance evidence**

- R1. A successful canary must demonstrate a genuine provider-confirmed changed-record correction from source commit S to fresh commit C, followed by acceptance and WebProtégé fidelity for C. Trace: origin U7/U10, F1–F3, R14–R20a.
- R2. Missing or mismatched lineage and an observed change to the reviewed PR endpoints must prevent acceptance; checks and signed evidence remain bound to the exact reviewed content. Trace: origin R17, R20a, R22–R23 and U7 stale-run scenarios.
- R3. The canary must distinguish local verification, historical keyless dispatch, waiting/failed live runs, and full live success in its durable receipt and top-level continuity files. Trace: origin R19–R20a; `AGENTS.md`.

**Preservation and lane limits**

- R4. All existing tests and trust boundaries remain intact; added tests execute without provider calls, credentials, or network access. Trace: origin R21–R24 and supplied campaign R15/R16 guardrails.
- R5. Lane work stays on `drawdown/foli-1` and remains local, with no credential access, spend, security-setting changes, production data changes, destructive cleanup, new service, schema migration, or package release. The live phase requires separate prerequisite satisfaction outside this sandbox. Trace: supplied campaign R11/R17/R19/R20 and the current stage instruction.
- R6. Provider choices, qualification thresholds, legacy-debt policy, and model independence remain unchanged. Trace: origin R6–R13 and R25; Release B belongs to `foli-2`.

### Scope Boundaries

The active local work consists of behavioral workflow tests, observed-stale acceptance rejection, and a canary runbook with a reviewable fixture specification.
No production ontology or generated WebProtégé file changes belong in this branch.

**Considered and not built:** An explicit self-dispatch continuation is unnecessary to establish the current canary contract. It introduces another dispatch owner and duplicate-spend handling; evidence that the existing approval-assisted PR path cannot run would justify reconsideration. A generalized retry scheduler or readiness-reporting subsystem is likewise unnecessary for this bounded verification.

#### Deferred to Follow-Up Work

- `foli-2`: provider/model changes and independent-provider qualification work beyond exercising the existing policy.
- `foli-4`: reproducible offline canary/readiness reporting. Existing replay remains part of U10 acceptance here.
- Other mandate items, ontology content repairs, and upstream contribution follow-ups remain outside this execution slice.

### Acceptance Examples

- AE1. Covers R1/R3. The October 20 waiting run is recorded as completed keyless evidence; it cannot satisfy provider-backed or WebProtégé acceptance.
- AE2. Covers R1/R2. A source run uploads four correction files for S; the corrected PR run completes for C; the trigger discovers the source run; fresh review restores the exact files and accepts only C.
- AE3. Covers R2. If the PR head, base, or repository changes while review runs, the final checks reject observed stale state and publish no successful stable check for that attempt.
- AE4. Covers R3/R5. With no provider budget or required approval available, U1–U3 can finish locally; U4 remains explicitly unverified with its missing prerequisites recorded.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Keep the existing event chain and record its approvals.** Current GitHub documentation allows token-created or updated PR workflows to wait for approval; token push alone is not proof of progression. Use the existing PR deterministic run, automatic trigger, and protected dispatch. Do not add a PAT, GitHub App, alternate trigger, or approval bypass. This serves R1/R4. [GitHub event rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
- KTD2. **Test actual orchestration with fake external commands.** Execute the relevant YAML shell blocks in temporary directories with fixture responses and command recording. Keep all existing contract tests and add behavior tests, following `docs/solutions/integration-issues/keyless-canary-for-workflow-run-dispatch-chain.md`. These tests prove local decisions; real Actions receipts prove platform behavior. This serves R2/R4.
- KTD3. **Refresh live endpoints at acceptance boundaries.** Check the PR head, base, and candidate repository before evidence publication, immediately before signing, and before publishing a successful stable check. API failure rejects acceptance. Independent API calls cannot make publication atomic with PR mutation; immutable SHA/hash binding prevents old evidence from authorizing newer bytes. This serves R2 without changing permissions or concurrency.
- KTD4. **Use a disposable same-repository canary branch and an aligned WebProtégé base.** The trusted producer stays on protected default-branch code. After C is accepted, the existing consumer can be manually dispatched on the fixed canary branch, with its actual run SHA and ontology hash verified. Confirm workflow/script code matches the reviewed default-branch revision; never merge the synthetic defective candidate. This serves R1/R5. [Manual workflow dispatch](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
- KTD5. **Continue local work while live prerequisites remain unavailable.** Record genuine blockers for later action, with no user time required through 2026-10-30 (session-settled: user-directed — chosen over waiting for Damien: the campaign requires autonomous progress). This governs R3/R5 and U1–U4.

Campaign execution also carries forward the user-directed Astra choice over a Sol-first ladder, guarded merging of expansions over routine human holds, and durable hygiene over speculative features. This item is planned work; those choices do not enlarge its scope or authorize spend.

### High-Level Technical Design

```mermaid
sequenceDiagram
    participant PR as Disposable canary PR
    participant D as Deterministic workflow
    participant T as Automatic trigger
    participant Q as Protected QA workflow
    participant E as Evidence and attestation
    participant W as WebProtege consumer
    PR->>D: Source S and baseline B
    D->>T: Successful PR run
    T->>Q: Dispatch immutable S/B inputs
    Note over Q: Existing environment approval required
    Q->>E: Upload verified correction lineage for S
    Q->>PR: Push corrected C; fail S check
    Note over PR,D: Approve automation-created PR run if required
    PR->>D: Corrected C
    D->>T: Successful fresh PR run
    T->>Q: C/B plus source run and S
    Q->>E: Restore exact source lineage
    Q->>Q: Fresh provider review and endpoint fences
    Q->>E: Accepted bundle and signed C evidence
    E->>W: Verify signature, replay, then graph fidelity
```

### Assumptions and execution dependencies

The historical fork environment is reported as main-only, reviewer-gated, and empty of provider secrets.
Its current state must be verified by the controller through authorized metadata access; this lane does not look for credentials or a login.
GitHub approval requirements and actual provider behavior are live checks, not local assumptions of success.

The repository policy's configured cost ceiling is not spend authorization.
Qualification, legacy surveillance, or provider disagreement may prevent a full pass even with credentials available.
Preserve those failures under R6; do not tune the policy to obtain a green canary.

The chief campaign excerpts and a Cockpit scanner capable of attributing this checkout to repository ID `folio` are unavailable in this sandbox.
The controller must provide or verify the authority excerpts before build and run the real scanner before closing the handoff.
File naming and `STATE:` lines can be checked locally, but they do not substitute for scanner attribution.

---

## Implementation Units

### U1. Execute the existing correction handoff in isolated tests

**Goal:** Establish behavior at the shell/API boundaries the historical text tests did not exercise.

**Requirements:** R1/R2/R4; AE2; origin U7/U10. **Dependencies:** Controller authority check.

**Files:** Add `tests/test_workflow_execution.py`; read and preserve `tests/test_workflow_contract.py`; exercise `.github/workflows/ontology-hydration-qa-trigger.yml` and `.github/workflows/ontology-hydration-qa.yml`.

**Approach:** Follow KTD2. Use the repository's YAML step extraction pattern and Python temporary-directory fixtures. Substitute fixed test values for Actions expressions, place fake `gh`/`git` commands ahead of real commands, and fail on any unexpected invocation. Use Bash and jq as the workflows do; both are present in this planning environment. Do not permit network fallback or silently skip the new coverage when a prerequisite is missing.

**Execution note:** Characterize current behavior first. Keep new checks for the missing final fence failing until U2 implements it; preserve existing assertions unchanged.

**Test scenarios:**

1. A successful fresh PR run for C discovers an unexpired `ontology-correction-S` artifact, then dispatches the protected workflow with exact C/B/PR/repository/source-run/S values. Cover AE2.
2. Pagination finds `FOLIO.owl` on a later files page; an unrelated-file PR causes no dispatch.
3. A changed live PR head, missing source artifact, or API failure prevents dispatch.
4. Restoration rejects a wrong source workflow/event/branch, wrong first parent, missing lineage file, or corrected-byte mismatch before invoking model QA.
5. Restoration preserves all three source/ledger/evidence runner arguments and the original candidate bytes on the valid path.
6. Correction upload and old-SHA failure precede the push; the correction-producing path does not sign or publish successful acceptance. Keep the existing opposite-guard tests.

**Verification:** Command logs establish the actual values, order, and fail-closed outcomes. No provider, GitHub, or registry operation occurs. Existing replay and attestation tests remain the content-integrity authority.

### U2. Reject observed stale endpoints before acceptance

**Goal:** Close the final endpoint-check gap required by origin U7.

**Requirements:** R2/R4; AE3. **Dependencies:** U1.

**Files:** Update `.github/workflows/ontology-hydration-qa.yml`; extend `tests/test_workflow_execution.py`; preserve `tests/test_workflow_contract.py`.

**Approach:** Apply KTD3 within the existing publication steps. Reuse the initial immutable endpoint checks and existing `GH_TOKEN` permission scope. Re-check only for an attempt otherwise eligible for success. On stale or unavailable endpoint data, preserve bounded diagnostics and publish failure rather than exiting before a negative check can be attempted. Keep correction/acceptance guards, source-SHA check binding, signer identity, and content hashes unchanged.

**Test scenarios:**

1. Matching live head/base/repository passes each fence and targets the stable check at the reviewed SHA.
2. A head, base, or repository change between initial review and publication prevents bundle publication and success. Cover AE3.
3. Movement after upload but before signing prevents signing; movement observed after signing prevents a successful stable check. Already published immutable evidence is not deleted or represented as revoked.
4. Failed/malformed PR metadata rejects acceptance and still attempts a failed stable-check result; check-publication failure never counts as acceptance.
5. The correction-producing path still fails S and produces no acceptance; no new token permission, environment change, or candidate-code execution enters the trusted job.

**Verification:** New behavioral regressions pass and all original workflow assertions still pass. The receipt describes the remaining non-atomic observation window honestly.

### U3. Prepare the bounded live-canary procedure

**Goal:** Make the live run concrete and reviewable without changing production ontology data.

**Requirements:** R1/R3/R5/R6; AE1/AE4; KTD4/KTD5. **Dependencies:** U1/U2 for final workflow expectations; drafting can proceed earlier.

**Files:** Add `docs/ontology-qa-release-a-canary.md`; update the scoped residual in `docs/residual-review-findings/automated-ontology-qa.md`, `STATUS-ONTOLOGY-QA.md`, and `NEXT-ONTOLOGY-QA.md`.

**Approach:**

1. Specify one existing-class annotation mutation that passes deterministic validation but gives independent providers a genuine semantic defect to assess. Record the exact baseline, triple, expected changed-record identity, and minimal candidate patch in the runbook. Choose a public, non-sensitive example distinct from scored benchmark cases; introduce no new IRI. Fixture selection is completed during build after local census verification, not guessed to guarantee provider agreement.
2. Specify the disposable fork PR and the existing approval-assisted transitions in KTD1. Keep candidate changes confined to ontology data and document code-identity checks for branch consumer execution.
3. Verify how the WebProtégé base represents B. Use the committed base only if its relevant semantics align; otherwise prepare a retained disposable export for the workflow's existing ZIP input, through an already authorized location. An unavailable aligned base is a recorded prerequisite, not permission to add storage or weaken fidelity.
4. Define one source attempt and one corrected-head review as the canary attempt. Further corrections, ambiguous dispatch, disagreement, budget exhaustion, or missing approvals end that attempt without success; do not repeatedly rerun it. Inspect existing run IDs before any recovery to avoid duplicate spend.
5. Provide the U4 receipt fields and the decision entries below. Preserve branch, source, baseline, and artifacts; close a disposable PR only after evidence is retained, and do not delete branches or artifacts as routine cleanup.

**Test expectation:** The runbook itself needs no new prose-mirroring tests. Verify the candidate patch locally with the existing delta/census tools during build, then prove its provider behavior only in U4. No live action occurs to validate documentation in this lane.

**Verification:** Another operator can identify exact inputs, approvals, expected artifacts, stop conditions, and recovery evidence without inventing a new workflow. R3 distinguishes prepared work from observed live outcomes.

### U4. Run the authorized real canary and retain its receipt

**Goal:** Produce the live evidence that closes origin U7/U10.

**Requirements:** R1–R6; AE2/AE4; KTD1/KTD4/KTD5. **Dependencies:** U1–U3, controller publication of reviewed workflow changes, and all live prerequisites below. This unit is not executable in the current sandbox or under the lane's no-spend rule.

**Files:** Create `docs/plans/evidence/foli-1-release-a-actions-canary.md` from actual observations; update `STATUS-ONTOLOGY-QA.md`, `NEXT-ONTOLOGY-QA.md`, and `docs/residual-review-findings/automated-ontology-qa.md` to match the result.

**Approach:**

1. Verify current default-branch workflows, existing protections, required-check configuration, authorized budget, provider readiness, and evidence-store access without disclosing secret values. Missing or changed security configuration is a blocker; this item does not change it.
2. Execute the runbook's disposable canary, collecting PR and run identities at every transition. Record any required automation-run and environment approvals. Waiting, skipped, cancelled, failed, or merely uploaded states are not full success.
3. Retain the original S, baseline B, corrected C, C's first parent, source run/attempt, correction artifact ID and hashes, and the four exact files: `correction-source.owl`, `corrected.owl`, `correction-ledger.json`, and `correction-evidence.json`.
4. Prove actual artifact discovery by the fresh PR trigger and exact lineage restoration in the fresh protected run. Retain real provider/qualification receipts and successful stable-check identity on C; S must remain unsuccessful.
5. Verify signed acceptance and retrieve the existing GHCR evidence bundle by its recorded reference; verify its digest and offline replay. The workflow writes a real evidence artifact and attestation; this is an existing U7 operation, not a new release mechanism or service.
6. Run the existing WebProtégé consumer against C under KTD4. Retain actual run SHA, input/base hashes, signature and replay results, output artifact identity/hash, and successful semantic fidelity verification.
7. Write a public-safe receipt of observed results, including failure stages. Mark the full canary complete only when every live gate below passes; otherwise leave its action open. The controller verifies Cockpit attribution to `folio`.

**Verification:** Real Actions run links and retained content hashes establish the whole chain. Local stubs cannot satisfy this unit. No benchmark or model-policy change is made to turn an inconclusive run into a pass.

---

## Verification Contract

No commands in this section were executed during planning.

| Gate | Applies to | Evidence required |
|---|---|---|
| Starting-state check | U1 | Re-read branch/status and relevant workflow changes before build; do not reuse historical test counts |
| Focused regression | U1/U2 | `python -m pytest -q tests/test_workflow_execution.py tests/test_workflow_contract.py tests/test_trusted_changed_record_corrections.py tests/test_correction_evidence.py tests/test_webprotege_attestation.py tests/test_webprotege_fidelity.py tests/test_safe_evidence_extract.py tests/test_evidence_replay.py` |
| Full suite | U1/U2 | `python -m pytest -q tests` with all existing tests retained; dependencies from `scripts/requirements.txt` and existing CI setup |
| Workflow and patch validity | U1–U3 | All three workflows remain valid YAML, added shell fragments parse, and `git diff --check` passes |
| Fixture preparation | U3 | Exact B/S delta and deterministic result recorded; published `FOLIO.owl` and generated output remain unchanged in the lane |
| Correction transition | U4 | Real source and fresh PR runs, approval states, correction artifact identity, C parent S, and byte-identical restored correction |
| Provider acceptance | U4 | Genuine independent-provider evidence, passing existing qualification/review policy, complete lineage, and successful C stable check |
| Durable handoff | U4 | Verified signature/provenance, archive digest, complete offline replay, real consumer run, and passing output graph fidelity |
| Continuity | Each milestone | Accurate `STATE:` and only open actions in top-level NEXT; real scanner output assigns them to `folio` |

---

## Live Prerequisites and Decisions

The controller authority cross-check precedes local build; provider access, budget, and required approvals hold only U4.
The controller can complete its checks independently. No action is requested from Damien through 2026-10-30.

| Needed | Owner and setting | Estimated active time | Unblocks |
|---|---|---|---|
| Verify chief Goal Capsule and campaign R11/R15/R16/R17/R19/R20; provide any missing constraint | Controller, chief checkout | 5 minutes | Build authorization cross-check |
| Publish reviewed branch and run Cockpit scanner for repository ID `folio` | Controller, authorized campaign environment | 5 minutes | Remote workflow availability and verified continuity |
| Supply authorized provider access in the existing protected environment and approve a bounded live budget; credential provisioning remains outside the lane | Damien or authorized account owner, browser with logins | 10 minutes | Real source and fresh-SHA model reviews |
| Satisfy existing Actions automation-run/environment reviewer gates when runs are ready | Required reviewer, browser with logins | 5 minutes across the attempt, excluding runner wait | Progress through the existing event chain |

Provider availability, existing policy qualification, aligned WebProtégé input, and registry/OIDC access are execution checks.
If one fails, record its exact failed stage and required remedy; do not assume that more budget or an alternate model will fix it.
The prior handoff's proposed model substitutions and cost estimates are not adopted by this plan.

---

## Definition of Done

The **local build** is complete when U1–U3 pass their verification, the change is reviewed, and the focused commits are ready for controller publication on `drawdown/foli-1`.
No abandoned implementation experiments, unrelated changes, weakened tests, or machine-local paths belong in the final diff.

The **foli-1 item** is complete only when U4 proves the actual correction-to-fresh-SHA transition, accepted signed evidence, and WebProtégé fidelity, with retained receipts and verified Cockpit attribution.
If live prerequisites remain unavailable, report the local work as complete and the live canary as unverified; retain its genuine NEXT action and the decision entries.

---

## Sources and Research

- Origin `docs/plans/2026-07-30-001-feat-automated-ontology-qa-plan.md`: Goal Capsule, U7/U10, cited requirements, verification contract.
- `docs/plans/2026-10-20-1500-ops-release-a-keyless-canary-plan.md` and `docs/handoffs/2026-10-20-release-a-canary-and-qa-residuals.md`: completed keyless receipt and remaining provider-backed work.
- `docs/solutions/integration-issues/keyless-canary-for-workflow-run-dispatch-chain.md`: real API/CLI failures missed by text tests.
- `docs/solutions/logic-errors/merge-pipeline-reported-changes-it-never-applied.md`: verify generated semantics, not reported change counts.
- `docs/solutions/conventions/minting-folio-concept-iris.md` and `docs/FOLIO-CHANGE-POLICY.md` (marked proposed): preserve identities and classify actual annotation changes; this plan adopts no release-policy expansion.
- [GitHub environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments): retain existing gates before secret-bearing execution.
- [GitHub attestation verification](https://cli.github.com/manual/gh_attestation_verify): verify provenance and the repository's custom acceptance predicate; a signature alone is insufficient.
