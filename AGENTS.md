# Repository Agent Instructions

## Cockpit continuity

Cockpit assigns this checkout to the `folio` repository section and scans only
top-level Markdown files whose names begin with `RESUME`, `HANDOFF`, `STATUS`,
`STATE`, or `NEXT`.

For every material implementation milestone, blocker, release-state change, or
handoff:

1. Update the appropriate top-level `STATUS-*.md` file with completed work,
   evidence, decisions, constraints, and residual risks.
2. Update the corresponding top-level `NEXT-*.md` file with only genuine open
   actions. Every Markdown bullet in a `NEXT-*.md` file becomes a Cockpit backlog
   item, so do not put completed-work summaries there.
3. Include a `STATE: ...` line that gives Cockpit a concise current state.
4. Verify the Cockpit scanner attributes the state and actions to repository ID
   `folio` before completing the handoff.

Do not rely on `.claude/RESUME.md`, `.compound-engineering/`, or another hidden
directory for Cockpit reporting; Cockpit does not scan those locations.
