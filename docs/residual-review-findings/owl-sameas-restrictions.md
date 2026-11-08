# Class restrictions on built-in and invented W3C terms

_Recorded 2026-11-08 during the FOLIO-to-OpenGloss mapping work; expanded the same day. Issues are
disabled on the damienriehl/FOLIO fork, so this file is the record. Counts are at `main` `b611c1c`._

## Finding

FOLIO states class-level relations as `rdfs:subClassOf` an `owl:Restriction` (`owl:onProperty` +
`owl:someValuesFrom`). With FOLIO's own object properties, that is ordinary, valid OWL, and most
restrictions in the file take that form. Four groups put the same construct on terms that cannot
carry it:

| Property in `owl:onProperty` | Restrictions | Classes | Problem |
|---|---:|---:|---|
| `rdfs:seeAlso` | 3,677 | 1,936 | An annotation property; using it in a class axiom puts the file in OWL Full. |
| `rdfs:locatedIn` | 231 | 188 | Not an RDFS term; minted inside the W3C RDFS namespace. |
| `owl:sameAs` | 217 | 217 | A built-in relating individuals, not a class crosswalk; the file also redeclares it as an `owl:ObjectProperty`. |
| `owl:isAuthor` | 6 | 3 | Not an OWL term; minted inside the W3C OWL namespace. |

The `owl:sameAs` group is what first surfaced:
- **PACER:** 18 of the 217 are PACER Nature-of-Suit classes. For example, *485 Telephone Consumer
  Protection Act (PACER NoS)* points to *Telephone Consumer Protection Act Claim*.
- **Field names:** most of the rest are billing and data-field names (`inv_total_net_due` →
  *Invoice Total Net Due*).
- **Renamed bodies:** some are renamed bodies (*U.S. Customs Court* → *U.S. Court of International
  Trade*).

Their intent reads as a crosswalk from a code or alias to the FOLIO concept.

## Why it cannot be fixed one group at a time

`folio-python` 0.4.0, ALEA's published client (`folio/graph.py`, the class parser), reads the
`rdfs:seeAlso` restriction pattern on purpose. It turns each one into an entry in the class's
`see_also` list and an `rdfs:seeAlso` triple. It ignores the `owl:sameAs` restrictions, so no
`folio-python` consumer sees those links today. That has three consequences:

- **sameAs alone:** rewriting only the 217 `owl:sameAs` restrictions (for example, into
  `skos:exactMatch` or `skos:closeMatch` annotations) would break no `folio-python` consumer, but it
  would leave FOLIO using two conventions for the same kind of link.
- **seeAlso:** rewriting the `rdfs:seeAlso` group into plain `rdfs:seeAlso` annotations would break
  `folio-python`'s see-also lookups unless the client changes in step.
- **Policy cost:** under `docs/FOLIO-CHANGE-POLICY.md`, each rewrite removes a class axiom (H-remove
  for any consumer that materialized it) and adds an annotation (A-add). It needs a version boundary,
  notice, and an affected-pair count.

The fix is a modeling-convention decision for FOLIO's maintainers, coordinated with a
`folio-python` release, rather than a local cleanup.

## Suggested direction (not applied)

1. **Agree the target forms:**
   - **Code and alias crosswalks** (the `owl:sameAs` group): SKOS mapping annotations, the
     predicate chosen per pair.
   - **Renamed bodies:** `dcterms:isReplacedBy`.
   - **Related-concept links** (the `rdfs:seeAlso` group): plain `rdfs:seeAlso` annotations.
   - **Location and authorship:** FOLIO-namespace object properties in place of the invented
     `rdfs:locatedIn` and `owl:isAuthor`.
2. **Ship the client first:** a `folio-python` release that reads both the old and the new forms.
3. **Then the ontology:** one versioned FOLIO release that rewrites all four groups, with a changelog
   and per-group counts.

The FOLIO-to-OpenGloss mapping module copies none of these patterns.
