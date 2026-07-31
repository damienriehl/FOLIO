from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
QA = ROOT / ".github/workflows/ontology-hydration-qa.yml"
MERGE = ROOT / ".github/workflows/webprotege-merge.yml"
TRIGGER = ROOT / ".github/workflows/ontology-hydration-qa-trigger.yml"
TRUSTED_RUNNER = ROOT / "scripts/run_trusted_ontology_qa.py"


def text(path):
    return path.read_text(encoding="utf-8")


def test_pr_path_has_no_secret_bearing_model_step():
    workflow = text(QA)
    assert "pull_request_target" not in workflow
    deterministic = workflow.split("trusted-model-review:", 1)[0]
    assert "OPENAI_API_KEY" not in deterministic
    assert "GOOGLE_API_KEY" not in deterministic


def test_trusted_job_executes_only_protected_runner_code():
    workflow = text(QA)
    trusted = workflow.split("trusted-model-review:", 1)[1]
    assert "path: trusted-runner" in trusted
    assert "python trusted-runner/scripts/run_trusted_ontology_qa.py" in trusted
    assert "python inputs/" not in trusted
    assert "ref: ${{ github.event.repository.default_branch }}" in trusted
    assert TRUSTED_RUNNER.is_file()


def test_stable_check_stale_fence_and_failure_evidence_exist():
    workflow = text(QA)
    assert "-f name=ontology-hydration-qa" in workflow
    assert "Fence stale completion" in workflow
    assert "if: failure()" in workflow
    assert "cancel-in-progress: true" in workflow


def test_successful_pr_check_automatically_dispatches_trusted_review():
    workflow = text(TRIGGER)
    assert "workflow_run:" in workflow
    assert "workflow_run.event == 'pull_request'" in workflow
    assert "workflow_run.conclusion == 'success'" in workflow
    assert "gh workflow run ontology-hydration-qa.yml" in workflow
    assert "candidate_repository=" in workflow
    assert ".filename == \"FOLIO.owl\"" in workflow


def test_acceptance_is_oidc_signed_and_durably_published():
    workflow = text(QA)
    assert "uses: actions/attest@v4" in workflow
    assert "id-token: write" in workflow
    assert "oras push" in workflow
    assert "ghcr.io/" in workflow


def test_confirmed_debt_correction_evidence_is_generated_by_protected_runner():
    workflow = text(QA)
    assert "inputs/correction-ledger.json" in workflow
    assert "inputs/correction-evidence.json" in workflow
    assert "--correction-ledger" in workflow
    assert "run_confirmed_defect_corrections.py" in workflow
    assert "cmp inputs/generated-candidate.owl inputs/candidate.owl" in workflow
    assert "contents/$CORRECTION_ROOT" not in workflow


def test_webprotege_requires_signature_and_offline_replay():
    workflow = text(MERGE)
    verify_at = workflow.index("gh attestation verify")
    replay_at = workflow.index("verify_acceptance_handoff.py")
    merge_at = workflow.index("python scripts/generate_webprotege_merge.py")
    assert verify_at < replay_at < merge_at
    assert "oras pull" in workflow
    assert "verify_webprotege_fidelity.py" in workflow


def test_workflows_are_valid_yaml_mappings():
    # PyYAML treats the YAML 1.1 word `on` as boolean; mapping shape is still
    # sufficient here because GitHub performs the authoritative syntax check.
    assert isinstance(yaml.safe_load(text(QA)), dict)
    assert isinstance(yaml.safe_load(text(MERGE)), dict)
    assert isinstance(yaml.safe_load(text(TRIGGER)), dict)
