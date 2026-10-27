# Hidden-label Search Coverage - Status

STATE: foli-5 plan reviewed; build awaits campaign authority verification; OntoKit acceptance unverified

Repository: `folio`
Last updated: 2026-10-27
Branch: `drawdown/foli-5`
Kind: expansion

## Planning outcome

The plan is `docs/plans/2026-10-27-0919-feat-hidden-label-search-coverage-plan.md`.
It scopes a portable RDF/XML and JSON acceptance corpus, producer regression tests, and an OntoKit acceptance handoff.
The existing label rebuild remains complete; downstream viewer implementation remains with `foli-3`.

## Evidence

Static inspection of `417a5e2ece96b011d4209986aa8a5a454c521cca` found all six approved Agreements hidden labels in both committed OWLs.
The French alternative `Accords` and untagged hidden `Accords` require distinct literal provenance; `Pact`/`Compact` are the proposed hidden-only search controls.
Current pytest discovery will include the planned test file without workflow or dependency changes.

The planning confidence check found no section requiring additional research.
Non-interactive document review completed with coherence, feasibility, scope, adversarial, and design reviewers: no findings, no fixes, and no decisions.
The optional cross-model document-review pass was disabled by checkout configuration; this is not a receipt for the campaign's later Astra/Fable build gate.

No implementation, repository tests, merge generation, provider calls, or viewer execution occurred in this planning stage.
No frontend changed, so no screenshot was produced.
Only the plan and this continuity pair are part of the delivery.
Publication is local only; the controller owns push, PR, and merge.

## Constraints and verification gaps

The chief checkout and `docs/plans/2026-10-26-0705-feat-codex-drawdown-campaign-plan.md` were unavailable.
The controller-supplied excerpts were preserved, but the Goal Capsule and campaign R11, R15, R16, R17, R19, R20 still require controller verification before the build.

Cockpit repository/scanner context is unavailable in this sandbox.
These top-level files follow `AGENTS.md` naming and `STATE:` conventions, but actual attribution to repository ID `folio` has not been verified.
The controller must run the real scanner; filenames alone are not an attribution receipt.

Current OntoKit source and test behavior have not been inspected.
A later FOLIO fixture pass will establish producer integrity only; consumer search, display, deduplication, and index refresh require a separate downstream receipt.
These are controller/downstream evidence tasks, not requests for credentials, spending, or a personal decision.
