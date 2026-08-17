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

## Documented solutions

`docs/solutions/` holds durable learnings from problems already solved here —
defects and near-misses alongside conventions and practices — filed in category
directories with YAML frontmatter (`module`, `component`, `problem_type`,
`tags`) so they can be searched by field as well as by content.

Relevant when implementing or debugging in an area someone has already been
burned by. Current entries cover this repository's IRI minting rules, which are
irreversible once published, and a class of silent-failure defect in the
WebProtégé merge pipeline.

Related durable context lives in `docs/handoffs/` (session-to-session state) and
`docs/FOLIO-CHANGE-POLICY.md` (what a given change obliges before shipping).
