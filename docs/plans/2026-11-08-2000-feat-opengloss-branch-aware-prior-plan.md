---
title: "feat: branch-aware domain prior for the OpenGloss mapping set (0.2.0)"
type: feat
status: active
date: 2026-11-08
origin: docs/plans/2026-11-08-1830-feat-opengloss-mapping-module-plan.md (set 0.1.0)
---

# Branch-aware domain prior (set 0.2.0)

## Problem

Set 0.1.0 scores each OpenGloss sense with one domain prior for every FOLIO class: law and
government 1.0, business 0.7, everything else 0.3. That prior assumes every FOLIO class is a legal
concept. FOLIO has large branches that are not legal: Location holds 3,783 classes, Industry and
Market 2,184, Language 490, and Currency 179. In those branches the right sense usually sits in a
non-legal domain.

- **Domain shares:** the set links 90% of the available legal senses but only 3% (324 of 11,941) of
  the senses in other domains.
- **Examples:** *Aquaculture* (`aquaculture:noun:0`, science.biology) and *Cordillera* and
  *Littoral* (nature) go unlinked.
- **Gold set:** 27 of the 62 unlinked candidates were judged correct.

A flat "link any single-sense headword" rule would raise recall but import errors: *Nan*, a Thai
province, would link to `nan:noun:0`, the computing NaN.

## Decision

Key the domain prior to the FOLIO branch a class belongs to, meaning the child of `owl:Thing` it
descends from. A class in several branches takes the highest prior any of its branches gives the
sense. All other method rules and thresholds stay as they are. This is a method change, so the
method becomes `opengloss-lexical/0.2` and the set becomes 0.2.0.

| Profile | FOLIO branches | Priors by OpenGloss `domain_root` |
|---|---|---|
| `legal` (today's) | every branch not listed below | law_government 1.0, business 0.7, other 0.3 |
| `place` | Location | law_government 1.0, nature 1.0, people_society 1.0, history 0.7, other 0.3 |
| `commerce` | Industry and Market | business 1.0; science, technology, nature, health, arts, everyday_life, sports_recreation, education 0.8; law_government 0.7; other 0.3 |
| `finance` | Currency, Financial Concepts and Metrics, Asset Type | business 1.0, law_government 0.8, mathematics 0.7, other 0.3 |
| `language` | Language | language 1.0, humanities 0.8, people_society 0.8, other 0.3 |
| `technical` | Data Format, System Identifiers, Communication Modality | technology 1.0, language 0.8, business 0.7, law_government 0.7, other 0.3 |
| `service` | Service | business 1.0, law_government 1.0, technology 0.8, health 0.8, other 0.3 |

Branch IRIs (local names under `https://folio.openlegalstandard.org/`): Location
`R9aSzp9cEiBCzObnP92jYFX`; Industry and Market `R8f4qGdjxuiQary8OBpq8W9`; Currency
`R767niCLQVC5zIcO5WDQMSl`; Financial Concepts and Metrics `RhBgnef56iLBXYfPqWQE41`; Asset Type
`RCIwc6WJi6IT7xePURxsi4T`; Language `RDOvAHsvY8TKJ1O1orXPM9o`; Data Format `R79aItNTJQwHgR002wuX3iC`;
System Identifiers `R8EoZh39tWmXCkmP2Xzjl6E`; Communication Modality `R8qItBwG2pRMFhUq1HQEMnb`;
Service `RDK1QEdQg1T8B5HQqMK2pZN`.

Branches are identified by IRI, not label, so a relabel in FOLIO cannot silently change the
profile. Each mapping row's `comment` gains the profile name (`profile=place`), so a consumer can
see why a non-legal sense won.

## Keep rule (decided before measuring)

- **Measure precision on new links:** judge a stratified random sample of 60 links that 0.2.0 adds
  over 0.1.0, 15 per predicate where available, from glosses and FOLIO definitions alone.
- **Measure precision overall:** re-score the 0.1.0 gold set against 0.2.0. Estimate overall
  precision as the link-weighted mean of the retained links' precision and the added links'
  precision.
- **Keep 0.2.0** when added-link precision is at least 0.70, estimated overall precision is at least
  0.76 (0.78 less the heartbeat's 0.02 tolerance), and gold recall rises.
- **Otherwise, revert:** keep 0.1.0 and record the result in this plan.

## Units

- **U1:** `folio_forms` records each class's branch IRIs. `matcher` maps branches to profiles and
  profiles to priors, the comment carries the profile, and `METHOD_VERSION` moves to
  `opengloss-lexical/0.2`. Tests cover:
  - **Branches:** a Location class links a nature sense, and an Industry class links a science sense.
  - **Nan:** a Location class still rejects a technology sense.
  - **Unchanged:** a legal-branch class behaves exactly as in 0.1.0.
  - **Multi-branch:** a class in two branches takes the highest prior.
  - **Deterministic:** identical inputs give identical output.
- **U2:** bump `upstream.json` to set 0.2.0 and method 0.2, regenerate, validate, and diff against
  0.1.0 (added and removed counts by predicate and branch).
- **U3:** judge the added-link sample, append it to `eval/gold.tsv` under a labelled header, apply
  the keep rule, and write the 0.2.0 receipt.
- **U4:** update the README, STATUS, and NEXT files; review; PR; merge; send folio-resolve the new
  commit.

## Out of scope

- **Word links:** lifting the one-sense-per-word cap.
- **Model judgment:** model-assisted sense disambiguation.
- **FOLIO.owl:** any change to the ontology itself.
