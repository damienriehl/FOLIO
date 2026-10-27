# foli-6 - Remaining actions

STATE: foli-6 plan reviewed; build awaits controller authority reconciliation.

Repository ID: `folio`

- Controller: provide or reconcile the chief campaign plan's Goal Capsule and Campaign R11/R15/R16/R17/R19/R20 against `docs/plans/2026-10-27-0953-feat-folio-usage-documentation-plan.md` before build.
- Build lane: after authority reconciliation, execute the committed plan through `lfg` on `drawdown/foli-6`, preserving all existing tests and recording the required local verification.
- Controller: verify that the actual Cockpit scanner attributes these STATUS/NEXT records to repository ID `folio`, then handle campaign scanning, publication and the merge gate when the build is complete.
