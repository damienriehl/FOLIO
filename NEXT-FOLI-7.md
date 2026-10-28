# FOLIO Drawdown foli-7 - Next Actions

STATE: folio / foli-7 ready for controller source verification and the separate build stage

Repository ID: `folio`

- [ ] Controller: reconcile the chief campaign Goal Capsule and cited Campaign R11/R15/R16/R17/R19/R20 with the [foli-7 plan](docs/plans/2026-10-27-2109-chore-foli-7-maintainer-hygiene-plan.md), and verify the real Cockpit scanner attributes this state and these actions to repository ID `folio`; both sources were unavailable in the planning sandbox.
- [ ] Build lane: run `lfg` on `docs/plans/2026-10-27-2109-chore-foli-7-maintainer-hygiene-plan.md` on `drawdown/foli-7`, establishing a fresh runtime baseline before implementation and completing the plan's tests, audit, and documentation evidence.
- [ ] Controller: after the build handoff, scan and publish the branch, open the PR, collect hosted CI and required campaign reviews, and submit it to the campaign merge gate; the sandbox must not add a remote or acquire credentials.
