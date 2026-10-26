# Release A correction-to-fresh-SHA canary

This procedure closes origin U7/U10 only after a real Actions run proves the
correction, acceptance, replay, and WebProtégé handoff. Local tests and fixture
preparation do not satisfy those gates. Scope: `foli-1` and
`docs/plans/2026-10-26-1224-fix-foli-1-actions-canary-plan.md`.

## Evidence states

| State | What is established | What remains unproved |
|---|---|---|
| Historical keyless canary, 2026-10-20 | Deterministic run `39489387823`, trigger `39492121465`, protected dispatch `39492136725` | The protected run was cancelled before any step; no correction, signing, or consumer success |
| Local build, 2026-10-26 | Shell decisions, rejection paths, full test suite, and fixture preparation described below | GitHub action/event delivery and genuine provider behavior |
| Waiting, cancelled, skipped, failed, or incomplete live attempt | Only the transitions actually observed | Full canary success |
| Complete live canary | Every gate in the receipt table below passes | No claim of legal ground truth or atomic exclusion of later PR movement |

The local lane has no remote, GitHub login, provider authority, or spend
authorization. The controller publishes the reviewed changes and verifies the
chief campaign excerpts and Cockpit attribution to repository ID `folio`.
No action is requested from Damien through 2026-10-30.

## Prerequisites before a live attempt

1. Record repository, default branch, protected workflow revision **W**, and
   current PR baseline **B**. Verify the reviewed QA and trigger workflows are
   present on that default branch. Record the existing required-check rule for
   `ontology-hydration-qa`, environment protection, and workflow permissions.
   An absent protection is a prerequisite failure, not permission to change it.
2. An authorized account owner must supply provider availability in the existing
   protected environment and authorize a bounded budget for the existing model
   policy. Secret names or readiness can be recorded; never copy secret values.
   Preserve the current models, independence rules, qualification thresholds,
   legacy surveillance, and cost ceilings. A policy ceiling is not permission
   to spend. Qualification or surveillance failure ends the attempt.
3. Identify the existing required reviewers for protected runs and any approval
   of automation-created PR workflow runs. Do not bypass these gates or add a
   PAT, GitHub App, alternate dispatch owner, or new service.
4. Confirm existing registry/OIDC access and retain all artifacts before expiry.
   Confirm the WebProtégé base is aligned as described below. If an aligned
   export is needed and no already authorized location can supply the existing
   ZIP input, record that prerequisite; do not create storage infrastructure.
5. Inspect existing canary PRs and source/fresh run IDs before dispatching.
   One source attempt and one corrected-head review constitute this attempt.
   Ambiguous dispatch, another correction, provider disagreement, exhausted
   budget, or a missing approval ends it without success. Do not rerun blindly.

## Exact disposable fixture

Preparation used baseline revision
`417a5e2ece96b011d4209986aa8a5a454c521cca`. The implementation branch leaves its
`FOLIO.owl` and generated WebProtégé output unchanged. At live execution, retain
the actual immutable B; if its ontology hash differs, repeat preparation and
record new hashes rather than reusing these observations.

| Input | SHA-256 |
|---|---|
| Baseline `FOLIO.owl` | `c0f8ca58dad4227e89856d97a0344f45bec37289832837bd11c473dfdc7b44be` |
| Mutated candidate S ontology | `767d7918b8484f0480292a6c2468e9bcb0de38694126244c2913386193ba2592` |
| Committed WebProtégé base | `00433748eff3d4acd6b113c1a4d8be1359d57227867dee8343b00aa37440d219` |

The subject is the existing **Billable Hour** class,
`https://folio.openlegalstandard.org/R1PpxLN7jiSIvJVou8IjDG`. Replace only its
`http://www.w3.org/2004/02/skos/core#definition` literal, with no language or
datatype. No IRI, parent, label, or other annotation changes.

```diff
-        <skos:definition>Engagement fee model where a client pays for the legal service provider&apos;s number of expended hours.</skos:definition>
+        <skos:definition>Engagement fee model where a client pays a fixed amount regardless of the legal service provider&apos;s number of expended hours.</skos:definition>
```

This deliberately changes time-based billing into a fixed fee. It gives the
providers a semantic defect to assess; it does not prescribe their verdict or
replacement. A search of `qa/ontology/evals/` and `confirmed-defects.json` found
no matching subject or definition. Preserve the scored cases and policy.

Expected B-to-S delta: one `replaced` literal record, no unrelated semantic
drift. Its content-addressed identity is:

| Field | Value |
|---|---|
| `record_id` | `57cb263abad6b8c16225489729589180243c6c54de289de078932d23a1f06580` |
| `before_hash` | `b442c7abc2a9ea45f43463d2d190269b8aeffd083292902b1ad68bb7401c0bab` |
| `after_hash` | `8a03be0efd28fcc04550209c502588e25222f28e95663238750c3acbd7114f95` |

Local preparation independently compared all parsed annotation values: exactly
one was removed and one added, both at this locator. The existing
`build_hydration_manifest` also produced this record ID on the selected class,
with no unrelated drift in that scoped graph. The fixture's full bytes differ
only by the one replacement above. These checks establish the prepared mutation;
they do not stand in for the full canonical manifest required by live QA.
The full-size call on 172,062 triples did not return within 15 minutes and was
stopped with inputs preserved. Before any provider dispatch, complete a bounded
full-size manifest preflight in the execution environment and retain its result;
if it does not complete, stop the attempt and investigate without reducing
coverage. This lane did not change the delta algorithm.

Prepare in a disposable same-repository canary branch based on the reviewed
default branch. Only ontology data may differ from W in the source candidate;
never merge this synthetic defective candidate. Retain the original B and S.
The following preparation writes a copy, not the checkout's ontology:

```bash
mkdir -p canary-evidence
git show "$BASELINE_SHA:FOLIO.owl" > canary-evidence/baseline.owl
python - <<'PY'
from pathlib import Path
p = Path('canary-evidence/baseline.owl')
old = b"Engagement fee model where a client pays for the legal service provider&apos;s number of expended hours."
new = b"Engagement fee model where a client pays a fixed amount regardless of the legal service provider&apos;s number of expended hours."
data = p.read_bytes()
assert data.count(old) == 1
Path('canary-evidence/candidate.owl').write_bytes(data.replace(old, new))
PY
python scripts/validate_ontology_annotations.py canary-evidence/candidate.owl \
  --baseline canary-evidence/baseline.owl --output canary-evidence/census.json
PYTHONPATH=scripts python - <<'PY'
import json
from pathlib import Path
from ontology_qa.delta import build_hydration_manifest
m = build_hydration_manifest('canary-evidence/baseline.owl',
                            'canary-evidence/candidate.owl',
                            run_id='canary-preparation', attempt_id='1')
assert m['payload']['record_count'] == 1
assert not m['payload']['unrelated_semantic_drift']
assert m['payload']['records'][0]['record_id'] == '57cb263abad6b8c16225489729589180243c6c54de289de078932d23a1f06580'
Path('canary-evidence/fixture-manifest.json').write_text(json.dumps(m, indent=2)+'\n')
PY
```

Keep preparation outputs out of the PR. Copy only the prepared candidate to
`FOLIO.owl`, commit S on the disposable branch, and open its same-repository PR.
Local census result: `complete`, 106,271 annotations inspected, zero new
failures, 199 inherited baseline failures, and 68 semantic-review risks. SHACL
conformance remains false because of inherited debt. The deterministic census
is baseline-relative: this result is not evidence of semantic correctness or a
reason to relax release policy.

## Source S to corrected C

1. Retain the PR number, B, S, source ontology hash, deterministic run, trigger
   run, and protected source run/attempt. The deterministic job must complete
   successfully before the automatic trigger dispatches the protected run.
   Record and satisfy existing environment approval; waiting is not success.
2. The source trusted run must find a genuine changed-record defect, generate a
   verified replacement, and upload `ontology-correction-S` **before pushing** C.
   Retain the artifact ID, source run identity, and exact files
   `correction-source.owl`, `corrected.owl`, `correction-ledger.json`, and
   `correction-evidence.json`, with SHA-256 for each. The source's stable check
   must be unsuccessful; the source correction path must not sign acceptance.
3. Record C and its first parent, which must be S. Preserve the exact correction
   commit message `fix(ontology): apply verified QA corrections`. If GitHub
   requires approval for the resulting PR workflow, satisfy that existing gate.
   A token push alone is not evidence that the fresh deterministic run happened.
4. Retain the fresh deterministic run, automatic trigger, and protected run.
   Show that the trigger selected the unexpired source artifact and dispatched
   **C/B/PR/repository/source-run/S**. Confirm source run workflow path, dispatch
   event, default branch, C's first parent, and all restored file hashes. The
   restored `corrected.owl` must equal the fresh candidate bytes exactly.
5. The fresh protected run must pass genuine qualification, dual-provider
   review, correction-lineage verification, legacy surveillance, and replay
   policy without further corrections. Retain its report, qualification and
   provider receipts, complete bundle, stable-check ID, and conclusion on C.
   A correction may return the annotation to B, making the final B-to-C delta
   empty; the genuine S-to-C correction lineage must still be retained and
   verified. Do not invent a new change to force a nonempty final delta.

## Acceptance and WebProtégé fidelity

The producer refreshes PR head/base/repository before bundle publication,
immediately before signing, and before publishing a successful stable check.
Observed movement or unavailable metadata rejects that attempt. Independent API
requests cannot lock a PR: movement after signing does not revoke already
published evidence. Exact commit/tree/content binding remains essential.
Endpoint diagnostics live beside the indexed bundle, never inside it.

Retain and verify the GitHub OIDC attestation with the producer identity
`REPOSITORY/.github/workflows/ontology-hydration-qa.yml`, the custom predicate
type `https://folio.openlegalstandard.org/attestation/ontology-qa/v1`, and the
actual default-branch workflow reference. Retrieve the existing registry bundle
at `ghcr.io/OWNER/REPOSITORY/ontology-qa-evidence:ONTOLOGY_HASH` (lowercase repository).
Use `safe_extract_evidence_bundle.py` with the predicate's archive digest, then
`verify_acceptance_handoff.py` with the recorded repository, candidate repository,
workflow reference, C, tree SHA, ontology, and archive. A signature alone is
insufficient. Reuse the exact verification commands in `webprotege-merge.yml`;
retain their outputs and digest rather than substituting a hand-built predicate.

The local committed WebProtégé base contains the exact baseline definition,
including literal metadata. A preparation-only merge of S changes that one
definition and passes XML/RDF validation. Before the live consumer, verify the
actual base-to-output graph difference against the **fresh accepted** manifest;
never substitute the source defect's B-to-S manifest. If B or the base changed,
repeat alignment checks. A required replacement export must be retained and
supplied through the workflow's existing `webprotege_zip_url` input from an
already authorized HTTPS location. Record URL provenance and content hashes
without credentials; do not weaken the fidelity verifier.

Manually dispatch the existing `webprotege-merge.yml` on the corrected disposable
branch. Before dispatch, verify its workflow and `scripts/`, `schemas/`, and
`qa/` code matches reviewed W, and that its head is still C. After dispatch,
verify the consumer's actual run SHA is C and its input ontology hash equals the
signed hash. Retain signature verification, archive digest, offline replay,
actual WebProtégé base hash, output hash, artifact ID, and the successful
`verify_webprotege_fidelity.py` result. A completed merge job or parse-valid file
without this fidelity result is insufficient.

## Receipt and stop conditions

Write `docs/plans/evidence/foli-1-release-a-actions-canary.md` only from actual
live observations. For an interrupted attempt, retain the failed/waiting stage
and the evidence obtained so far. Do not fill missing fields with local stubs.

| Gate | Required retained fields |
|---|---|
| Preparation | Repository, PR URL/number, W, B, S, fixture delta and ontology hashes; current protections and approval requirements |
| Source review | Deterministic/trigger/protected run URLs, run IDs/attempts, approval outcomes, provider/qualification receipts, unsuccessful stable check on S |
| Correction | C, parent S, source artifact ID and run, four file hashes, ledger and evidence identities |
| Fresh review | Fresh run URLs/attempts, observed trigger inputs, restored file hashes, complete report and successful stable check ID bound to C |
| Durable acceptance | Commit/tree/workflow/run identities, signed ontology hash, attestation identity, registry reference, archive digest, verified signature and offline replay output |
| Consumer | Actual run SHA C, input/base/output hashes, code-identity comparison to W, output artifact ID, successful semantic fidelity result |
| Continuity | Accurate top-level STATUS/NEXT, controller's real Cockpit scan attributing state and actions to `folio` |

Stop on a stale endpoint, missing/mismatched artifact, missing approval, provider
failure/disagreement, quarantine, budget exhaustion, another correction, missing
registry/OIDC capability, or replay/fidelity failure. Record the exact stage and
remedy before considering recovery; inspect run IDs to avoid duplicate spend.
Preserve B/S/C, branches, and artifacts. Close the disposable PR only after the
receipt and required evidence are retained; do not routinely delete anything.

## Needs your decision

These decisions hold the live attempt only; local implementation is complete.

| Needed | Setting | Active minutes | Unblocks |
|---|---|---|---|
| Authorized provider access and a bounded live budget under the existing policy, supplied by Damien or an authorized account owner | browser with logins | 10 | Real source and fresh-head reviews |
| Existing protected-environment and any automation-run approvals by the required reviewer | browser with logins | 5, excluding runner wait | Progress through the existing Actions chain |

Controller publication, chief-authority cross-check, and Cockpit scanner
verification are controller actions, not new requests for Damien's time.
