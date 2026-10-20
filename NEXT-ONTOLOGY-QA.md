# Automated Ontology QA — Next Actions

STATE: Release A complete — Release B awaits genuine cross-provider availability

- [x] [P1] Keyless partial canary on the fork (2026-10-20): deterministic job, trigger, and dispatch proven; three trigger bugs fixed (fork PRs #4 to #6).
- [ ] [P1] Run the full, model-bearing canary. It needs `OPENAI_API_KEY` and `GOOGLE_API_KEY` as `ontology-qa` environment secrets, which is a credential and spend decision for Damien, plus his approval of the waiting deployment. Until it runs, `WebProtégé Merge` on fork `main` fails closed for lack of an attestation.
- [ ] [P1] Begin Release B only after two genuinely available independent model providers can complete the qualification path.
- [ ] [P1] Resolve maintainer review on `alea-institute/FOLIO#16` and merge the Co-Investment Fund class after approval; Mike Bommarito's review is requested. The focused PR is one commit, one file, and does not carry the unpublished `automated-ontology-qa` work.
