# FOLIO - The Federated Open Legal Information Ontology

![FOLIO Logo](https://discourse.openlegalstandard.org/uploads/default/original/1X/ceb45b9ec0ef6f67cc516f9d5e30e9f6527eab44.png)

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


## Overview

[FOLIO (Federated Open Legal Information Ontology)](https://openlegalstandard.org) is an open, CC-BY licensed standard designed to represent universal elements of legal data. It improves communication and data interoperability across the legal industry by providing a comprehensive ontology and taxonomy for legal concepts.

## Repository Contents

- `FOLIO.owl`: The primary OWL (Web Ontology Language) file containing the FOLIO ontology
- `documentation/` (coming soon): Detailed documentation on FOLIO concepts and usage
- `examples/` (coming soon): Sample implementations and use cases

## Key Features

- **Comprehensive**: Over 18,000 standardized concepts covering a wide range of legal terms
- **Unique Identifiers**: Every concept has a unique IRI (Internationalized Resource Identifier)
- **Multilingual Support**: Translations for the ten most common languages
- **Open Development**: Collaboratively developed by legal professionals, technologists, and domain experts

## Getting Started

1. Clone this repository:
   ```
   git clone https://github.com/alea-institute/folio.git
   ```
2. Explore the `FOLIO.owl` file using an ontology editor like Protégé or WebProtégé
3. Refer to the documentation for implementation guidelines

## Use Cases

FOLIO can be applied in various legal technology scenarios, including:

- Contract Management
- Case Management
- Generative AI for legal applications
- Legal research and analytics
- Regulatory compliance

## Implementation

1. **Explore**: Review our documentation, tutorials, and examples
2. **Integrate**: Use the FOLIO OWL data or API in your systems and services
3. **Collaborate**: Share your experiences and contribute to improving the standard

## Contributing

We welcome contributions from the legal and technology communities. Please see our [CONTRIBUTING.md](CONTRIBUTING.md)(coming soon) file for guidelines on how to participate in FOLIO's development.

### Automated ontology QA

Changes to definitions, examples, or translations are fail-closed. Pull requests
run the full deterministic annotation census without secrets. A successful
census automatically dispatches the protected `Ontology Hydration QA` workflow
against the exact reviewed commit. That workflow runs only code from the
protected default branch; the candidate ontology is downloaded and handled
strictly as data. Maintainers can use `workflow_dispatch` to retry a failed
trusted run without weakening the identity checks.

The trusted workflow performs blind, qualified model review, publishes a stable
`ontology-hydration-qa` check, signs the accepted ontology with GitHub OIDC, and
stores its content-addressed evidence bundle in the repository's GitHub
Container Registry. Fork pull requests never receive provider credentials.
WebProtégé generation refuses ontology bytes without the matching signature and
an offline-replayable evidence bundle.

Local deterministic checks:

```bash
python -m pip install -r scripts/requirements.txt pytest jsonschema
pytest -q tests
python scripts/validate_ontology_annotations.py FOLIO.owl
```

### Minting IRIs for new concepts

FOLIO IRIs are permanent: once published, one is never deleted and never reused
(`docs/FOLIO-CHANGE-POLICY.md` §2). Generate them; never type one by hand.

```bash
python -m pip install -r scripts/requirements-authoring.txt
python scripts/mint_iri.py                  # mint one, with its sorted insertion point
python scripts/mint_iri.py --check <IRI>    # validate shape, and that it is unused
python scripts/mint_iri.py --audit          # IRI family census, and the drift gate
```

The generation algorithm itself lives upstream in
[folio-python](https://github.com/alea-institute/folio-python) (`folio/iri.py`):
`R` followed by base62 of 127 random bits, the scheme used by the great majority
of published FOLIO concepts. `scripts/mint_iri.py` carries no generator of its
own and refuses to run without folio-python, so there is one implementation
rather than two that can drift apart. What it adds is the part upstream cannot
know: collision checking against this working copy, the sorted insertion point,
and the family census.

`tests/test_iri_minting.py` ratchets against drift — it fails if a class IRI
appears that matches none of the known families. It skips when folio-python is
absent, so it does not yet gate CI; see `scripts/requirements-authoring.txt`.

Replay a downloaded durable evidence bundle without provider access:

```bash
python scripts/run_ontology_hydration_qa.py \
  --bundle evidence \
  --replay \
  --report-schema schemas/ontology-qa-report.schema.json
```

Confirmed legacy defects use the same automated, bounded path as new
hydration: two blind reviewers confirm the defect, a model proposes structured
replacement data, two cross-provider verifier routes approve the exact
replacement, and two cross-provider reviewers assess the corrected value. The
runner applies the complete batch to a disposable copy and publishes nothing
unless stale-write protection, deterministic validation, graph allowlisting,
and final rereview all pass:

```bash
python scripts/run_confirmed_defect_corrections.py \
  --source FOLIO.owl \
  --output corrected.owl \
  --ledger correction-ledger.json \
  --evidence correction-evidence.json \
  --cache .ontology-qa-cache
```

The ledger and evidence are canonical, append-only JSON. A trusted release that
closes confirmed debt must supply both with `--correction-ledger` and
`--correction-evidence`; offline replay reapplies them to the retained baseline
and requires byte-identical candidate output. Model receipts are cached by
provider, exact model, prompt, schema, policy, qualification, candidate, and
record payload. The evidence budget records request and token totals plus
projected cost.

The census is expected to fail while confirmed legacy debt remains open. Do not
weaken the policy or resample to obtain a pass. Provider, prompt, schema, rubric,
or threshold changes invalidate route qualification and require a new trusted
run. Trusted execution requires `OPENAI_API_KEY` and `GOOGLE_API_KEY` secrets in
the protected `ontology-qa` environment. Missing credentials, unsupported
locales, model disagreement, failed qualification, sampling expansion, or any
provider/budget failure blocks the check; there is no Claude route or fallback.
Production votes and correction-verifier votes must each span distinct
providers. Diagnose a blocked run from its census findings, qualification
artifacts, provider receipts, reconciliation states, surveillance strata, and
budget snapshot; never bypass a failed stage or substitute a same-provider
route.

## Community and Support

- [FOLIO Forum](https://discourse.openlegalstandard.org)
- [GitHub Issues](https://github.com/alea-institute/folio/issues)
- [FOLIO Blog](https://openlegalstandard.org/blog)

## License

The data in this repository is licensed under a [Creative Commons Attribution 4.0 International License][cc-by].

Any source is licensed under the MIT license.

[Prior versions of a related project](https://github.com/sali-legal/LMSS) were available under an MIT license. The list of all original contributors can be reviewed there.

---

For more information, visit [openlegalstandard.org](https://openlegalstandard.org).
