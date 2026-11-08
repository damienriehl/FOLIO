# owl:sameAs restrictions used as class crosswalks

_Recorded 2026-11-08 by the FOLIO-to-OpenGloss mapping work. Issues are disabled on the
damienriehl/FOLIO fork, so this file is the record; file it upstream when the fix is planned._

## Finding

`FOLIO.owl` links 217 classes to other FOLIO classes through an `owl:Restriction` on `owl:sameAs`:

```xml
<rdfs:subClassOf>
    <owl:Restriction>
        <owl:onProperty rdf:resource="http://www.w3.org/2002/07/owl#sameAs"/>
        <owl:someValuesFrom rdf:resource="https://folio.openlegalstandard.org/RsjSvqTnsUpWdxFUO18H3d"/>
    </owl:Restriction>
</rdfs:subClassOf>
```

`FOLIO.owl` also declares `owl:sameAs` as an `owl:ObjectProperty` with its own label.

**Counts at `main` 417a5e2.** 219 lines mention `owl#sameAs`. Two belong to the property declaration, and 217 are restrictions, one per class.
- **PACER:** 18 are PACER Nature-of-Suit classes. For example, *485 Telephone Consumer Protection Act (PACER NoS)* points to *Telephone Consumer Protection Act Claim*, and *01 Contract (PACER NoS)* points to *Contract & Quasi-Contract Claims*.
- **Data fields:** most of the rest are billing and data-field classes (`inv_total_net_due` → *Invoice Total Net Due*, `cl_matter_id` → *Client Matter ID*). Others are renamed bodies (*U.S. Customs Court* → *U.S. Court of International Trade*).

## Why it is a defect

`owl:sameAs` relates individuals, not classes. It is a built-in of the OWL language, so it should not be redeclared or used as an ordinary object property.
- **Under OWL 2 DL:** the restriction says each member of class A is identical to some member of class B. That is not the intended claim, "class A corresponds to class B".
- **Tooling:** some tools reject the file or drop the axiom, and a reasoner that keeps it can make unintended entailments.

The intent looks like a crosswalk between a code list (PACER NoS codes, billing field names, former court names) and the FOLIO concept.

## Suggested direction (not applied here)

Replace each restriction with a SKOS mapping annotation such as `skos:exactMatch`, `skos:closeMatch` or `skos:broadMatch`, chosen per pair, or with `dcterms:isReplacedBy` for the renamed bodies. Then remove the `owl:sameAs` property declaration.
- **Policy class:** under `docs/FOLIO-CHANGE-POLICY.md`, each replacement removes an axiom (H-remove for any consumer that materialized it) and adds an annotation (A-add). It needs a version boundary and a changelog entry.
- **Out of scope:** the FOLIO-to-OpenGloss mapping work (branch `feat/opengloss-mapping`) deliberately does not copy this pattern and does not fix it. The fix belongs in its own change.

