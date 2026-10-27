# foli-6 - Usage documentation planning status

STATE: foli-6 plan reviewed; implementation awaits controller campaign-source reconciliation.

Repository ID: `folio`

Item: `foli-6` (`expansion`)

Branch: `drawdown/foli-6`

Plan: [FOLIO Usage Examples and Documentation](docs/plans/2026-10-27-0953-feat-folio-usage-documentation-plan.md)

## Starting state and scope

Baseline: `417a5e2`.
Static inspection reconfirmed the two README “coming soon” entries and the absence of `documentation/` and `examples/`.
The existing Python 3.12 CI job runs the full `tests/` directory, and `scripts/requirements.txt` already includes RDFLib.

The plan covers consumer Markdown guides and three read-only examples: load and summarize classes, inspect labels and direct hierarchy, and run a fixed local SELECT query.
It specifies fixture coverage, real-corpus smoke checks, source-byte preservation and focused documentation-link checks for the build stage.
It does not implement another mandate item or change ontology data, workflows, services or deployment configuration.

## Evidence and verification

This is a planning-only stage: no tests, example execution or dependency installation has occurred.
No claim of a passing runtime baseline is made.
The confidence check found no sections needing strengthening.
Non-interactive `ce-doc-review` completed with no findings from coherence, feasibility, scope-guardian and adversarial reviewers; no review fixes or user decisions remain.
Automatic cross-model document review was disabled by the checkout's existing configuration; this does not waive the campaign's subsequent PR reviews.
The plan and these continuity records are the complete local plan-stage change; publication remains with the controller.

## Controller prerequisites and residuals

The chief source `docs/plans/2026-10-26-0705-feat-codex-drawdown-campaign-plan.md` is not available in this sandbox.
The plan uses the controller-supplied mandate and campaign rule references without claiming to have read the missing Goal Capsule or requirement text.
The controller must reconcile those excerpts before build.

The Cockpit scanner and its source checkout are unavailable here.
Actual scanner attribution to repository ID `folio` remains unverified; these top-level files follow the naming contract in `AGENTS.md` but do not replace that check.
No new decision or credential from Damien is needed for the proposed work.

Markdown and CLI examples introduce no frontend page, so screenshot evidence is not applicable to the current scope.
