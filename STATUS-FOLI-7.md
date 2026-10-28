# FOLIO Drawdown foli-7 - Status

STATE: folio / foli-7 implemented locally; dependency advisory lookup and hosted validation remain open

Repository ID: `folio`
Branch: `drawdown/foli-7`
Last updated: 2026-10-28

## Completed build

Implemented the [maintainer hygiene plan](docs/plans/2026-10-27-2109-chore-foli-7-maintainer-hygiene-plan.md):

- deterministic workflows share a bounded test manifest, explicitly verify the IRI module and required ontology files, run the entire suite, and report skips;
- command-level tests cover validator output/status/baselines and IRI check/audit/mint/no-file behavior;
- evidence tests cover unsafe archive types and roots, corrupt and empty input, atomic rejection, overwrite preservation, and replay/assembly failures;
- `CONTRIBUTING.md` now documents Python 3.12 setup, full tests, absolute versus baseline-relative census behavior, offline replay, and dependency auditing;
- the dated audit receipt contains the resolved local inventory, incomplete advisory disposition, and bounded workflow/evidence/provider source review.

One characterized wrapper defect was fixed: explicitly supplied ontology paths that do not exist now follow the documented no-files diagnostic and exit 2, rather than raising an unhandled `FileNotFoundError`.

## Evidence

Fresh baseline at `c6089a1`: `python -m pip check` reported no broken requirements, and `python -m pytest tests -q -ra` passed 191 tests in 52.79 seconds.

Final working tree: required `folio.iri` import and ontology-file checks passed; `python -m pip check` reported no broken requirements; and `python -m pytest tests -q -ra` passed 212 tests in 63.57 seconds with no skips.

The isolated audit install was attempted but package-index connections were rejected by the sandbox proxy. `pip-audit` therefore could not run and the receipt explicitly remains incomplete rather than claiming a clean result.

No ontology, schema, QA policy, prompt, migration, production data, credential, security setting, release, outside service, or trusted model job was changed.

## Residuals

The controller still owns campaign-source reconciliation, Cockpit scanner attribution, publication, hosted CI, and campaign reviews. A network-enabled maintainer environment must complete the advisory scan recorded in `NEXT-FOLI-7.md`; this needs no Damien decision or credential.
