---
title: WebProtege merge reported definition changes it never applied
date: 2026-08-17
category: logic-errors
module: webprotege-merge-pipeline
problem_type: logic_error
component: tooling
symptoms:
  - "Summary printed \"Total changes applied: 2\" on a run that applied 1"
  - A concept stayed diverged from FOLIO.owl across every regeneration, with no warning
  - An added second skos:definition overwrote the existing one instead of joining it
root_cause: logic_error
resolution_type: code_fix
severity: high
related_components:
  - documentation
tags: [webprotege, merge-pipeline, silent-failure, regex, data-loss, rdf-xml]
---

# WebProtege merge reported definition changes it never applied

## Problem

`scripts/generate_webprotege_merge.py` propagates content from the canonical
`FOLIO.owl` into a WebProtege export. Its definition-handling code contained two
independent defects that shared one shape: **the pipeline reported work it had
not done.** One left a concept silently diverged for months; the other destroyed
an existing definition while reporting success.

## Symptoms

- A run ends with `Total changes applied: 2` having applied 1. The count comes
  from the diff, not from the writes.
- `R5RoVVyRmkyMepjXK7X1sp` (No-Fault Claim) was reported as a pending definition
  update on every regeneration and never actually updated. It had carried
  WebProtege-only prose since the merge output was first committed.
- A class that gains a second `skos:definition` in `FOLIO.owl` comes out of the
  merge with one definition — the new one — and the pre-existing text is gone.

## What Didn't Work

- **Reading the summary.** It reports detections, so a failed apply is
  indistinguishable from a successful one. The run looks clean.
- **Trusting the internal counter.** `apply_changes` keeps an honest
  `changes_applied`, and its `log.info("Total changes applied: %d", …)` line
  did print `1`. But `print_summary` computed its own total from
  `len(diff.definition_updates)` and printed `2` a few lines later, so the
  truthful number was drowned by the untruthful one.
- **Making the regex attribute-tolerant, on its own.** This is the obvious fix
  and it is unsafe — see Prevention.

## Solution

Three changes, all in `scripts/generate_webprotege_merge.py`.

**1. Match attributed opening tags, excluding self-closing ones**
(`def_pattern`, near line 458). WebProtege writes `rdf:datatype` and `xml:lang`
on some definitions; the old pattern was a bare tag:

```python
# before — misses every attributed definition, then returns silently
def_pattern = re.compile(r"<skos:definition>.*?</skos:definition>", re.DOTALL)

# after — tolerant of attributes, and refuses self-closing tags
def_pattern = re.compile(
    r"<skos:definition(?![^>]*/>)(\s[^>]*)?>.*?</skos:definition>",
    re.DOTALL,
)
```

The replacement preserves group 1 (the attributes) rather than rewriting the
tag, so a datatype or language tag survives the content update. The `else`
branch now warns instead of falling through.

**2. Separate additions from replacements.** `compute_semantic_diff`
distinguishes a 1:1 replacement from an addition, but put both in
`definition_updates`. `apply_changes` read only that field and substituted in
both cases:

```
before: <skos:definition>Original</skos:definition>
after:  <skos:definition>Added second</skos:definition>   # "Original" destroyed
```

Additions now have their own field (`definition_additions`, set near line 225)
and their own apply step (`4b`, near line 484) that inserts before
`</owl:Class>` the way new altLabels already do.

**3. Report writes, not intentions.** `definitions_applied` and
`definitions_added` record what actually landed; the summary prints
`N applied of M detected` and marks any shortfall `NOT APPLIED`.

A shared `_literal_tag` helper (near line 592) serialises language tags and
datatypes in one place, so no insertion path can write `"x"` for a value that
is `"x"@fr-fr` — a different triple.

## Why This Works

The first defect is a **contract mismatch**: the apply step assumed a narrower
serialisation than the data actually contains. Of the 15,664 `skos:definition`
tags in the merge output, 9 carry attributes — 0.1%, which is exactly why it
survived review. It only ever mattered when a pending update happened to land
on one of those 9.

The second is a **type error expressed as a shared field**. "Replace this
definition" and "add this definition alongside the existing ones" need opposite
behaviour, and one field cannot encode which was meant. Splitting them removes
the ambiguity at the data model rather than patching the branch that read it —
a later reader cannot re-conflate two fields the way one overloaded field
invited. 87 classes in `FOLIO.owl` already carry more than one definition, so
nothing but the absence of a triggering commit had kept this from losing content.

Both were invisible for the same reason: **the summary counted detections.** A
report derived from intent rather than outcome cannot distinguish work done from
work attempted, so neither defect ever produced a failing signal.

## Prevention

- **Never make an XML tag regex attribute-tolerant without excluding
  self-closing tags.** This ontology contains four
  `<skos:definition rdf:resource="…"/>` tags pointing at YouTube and Tableau
  URLs. They have no closing tag, so a naive `.*?</skos:definition>` treats one
  as an opening tag and runs to the next closing tag it finds. Measured on the
  real file, that match spans 170 characters and would replace both the
  resource-valued definition and its sibling with a single string. It crosses no
  class boundary *there*, but nothing guarantees that: a block with no literal
  definition after the self-closing tag puts the next match a whole class away.
  Use a negative lookahead: `(?![^>]*/>)`.

- **Count what was written, not what was detected.** Any summary derived from
  the diff will report success for work that silently failed. Track applied
  items in a separate field and print `applied of detected`.

- **A regex `if match: apply` with no `else` is a silent failure.** Every apply
  path in this script that can fail to locate its target must warn. The label
  removal path already did this correctly and is the model to copy.

- **Test the apply step, not just the diff.** `compute_semantic_diff` detecting
  a change is not evidence that `apply_changes` writes it. The pre-existing
  characterization tests covered detection only, which is how both defects
  passed a green suite. `tests/test_webprotege_definition_apply.py` covers the
  apply step across all three opening-tag forms, attribute survival, both
  self-closing shapes, addition-versus-replacement, and applied-set tracking.

- **Verify a merge run by diffing the output**, not by reading the summary. The
  regeneration that exposed defect one produced a two-line diff while claiming
  two changes.

## Related Issues

- `docs/FOLIO-CHANGE-POLICY.md` — change classification and IRI permanence
- `NEXT-ONTOLOGY-QA.md` — records a remaining cosmetic issue in the same
  function: rdflib treats `"x"` and `"x"^^xsd:string` as distinct in set
  arithmetic though RDF 1.1 does not, so one definition is re-detected as
  pending on every run. Output is stable; it is summary noise, not churn.
- Fixes are on branch `automated-ontology-qa` and are not yet merged to
  `main` as of this writing.
