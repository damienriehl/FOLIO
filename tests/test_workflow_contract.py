from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
QA = ROOT / ".github/workflows/ontology-hydration-qa.yml"
TESTS = ROOT / ".github/workflows/tests.yml"
MERGE = ROOT / ".github/workflows/webprotege-merge.yml"
TRIGGER = ROOT / ".github/workflows/ontology-hydration-qa-trigger.yml"
TRUSTED_RUNNER = ROOT / "scripts/run_trusted_ontology_qa.py"


def text(path):
    return path.read_text(encoding="utf-8")


def steps(path, job):
    workflow = yaml.safe_load(text(path))
    return {
        step["name"]: step
        for step in workflow["jobs"][job]["steps"]
        if "name" in step
    }


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


def test_trigger_reads_pull_request_from_run_object():
    workflow = text(TRIGGER)
    assert 'actions/runs/$RUN_ID"' in workflow
    assert ".pull_requests[0].number" in workflow
    assert "/actions/runs/$RUN_ID/pull_requests" not in workflow


def test_trigger_never_combines_slurp_with_jq():
    workflow = text(TRIGGER)
    assert not any("--slurp" in line and "--jq" in line for line in workflow.splitlines())
    assert "--paginate" in workflow


def test_trigger_dispatch_names_repository():
    workflow = text(TRIGGER)
    dispatch = workflow.split("gh workflow run", 1)[1].split("-f pull_request_number", 1)[0]
    assert '--repo "$GITHUB_REPOSITORY"' in dispatch


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


def test_changed_record_correction_is_committed_and_rereviewed_at_fresh_sha():
    workflow = text(QA)
    assert "--corrected-output inputs/generated-correction/corrected.owl" in workflow
    assert "ontology-correction-${{ inputs.reviewed_sha }}" in workflow
    assert "git -C candidate-checkout add FOLIO.owl" in workflow
    assert 'push origin "HEAD:$HEAD_REF"' in workflow
    assert 'head_sha="$REVIEWED_SHA"' in workflow
    assert "-f conclusion=failure" in workflow
    assert 'test "$CANDIDATE_REPOSITORY" = "$GITHUB_REPOSITORY"' in workflow


def test_fresh_review_restores_and_verifies_correction_lineage():
    workflow = text(QA)
    assert "correction_run_id:" in workflow
    assert "gh run download" in workflow
    assert ".github/workflows/ontology-hydration-qa.yml" in workflow
    assert 'jq -r .event inputs/correction-run.json' in workflow
    assert "'.parents[0].sha'" in workflow
    assert "--correction-source inputs/correction-source.owl" in workflow
    assert "--correction-ledger inputs/correction-ledger.json" in workflow
    assert "--correction-evidence inputs/correction-evidence.json" in workflow
    trigger = text(TRIGGER)
    assert "correction_commit" in trigger
    assert "apply verified QA corrections" in trigger
    assert "actions/artifacts?name=ontology-correction-$CORRECTION_SOURCE_SHA" in trigger
    assert 'correction_run_id="${{ steps.endpoints.outputs.correction_run_id }}"' in trigger
    assert 'correction_source_sha="${{ steps.endpoints.outputs.correction_source_sha }}"' in trigger


def test_correction_and_acceptance_steps_have_opposite_guards():
    trusted = steps(QA, "trusted-model-review")
    correction_guard = "steps.qa.outputs.correction_ready == 'true'"
    acceptance_guard = "steps.qa.outputs.correction_ready != 'true'"
    for name in (
        "Upload verified correction lineage",
        "Checkout reviewed branch for verified correction",
        "Commit verified ontology bytes for fresh review",
    ):
        assert trusted[name]["if"] == correction_guard
    for name in (
        "Fence stale completion",
        "Publish durable evidence bundle",
        "Push durable evidence bundle",
        "Create acceptance predicate",
        "Sign acceptance with GitHub OIDC",
    ):
        assert trusted[name]["if"] == acceptance_guard
    assert acceptance_guard in trusted["Publish stable required check"]["if"]


def test_trigger_dispatches_correction_commit_with_lineage_inputs():
    trigger = steps(TRIGGER, "dispatch-trusted-review")
    dispatch = trigger["Dispatch protected model-bearing workflow"]
    assert dispatch["if"] == "steps.endpoints.outputs.ontology_changed == 'true'"
    command = dispatch["run"]
    assert "CORRECTION_ARGS" in command
    assert "correction_run_id=" in command
    assert "correction_source_sha=" in command


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
    assert isinstance(yaml.safe_load(text(TESTS)), dict)


def test_full_suite_workflows_share_fail_closed_test_setup():
    for path, job in ((TESTS, "pytest"), (QA, "deterministic-pr")):
        workflow = text(path)
        job_steps = steps(path, job)
        assert "scripts/requirements-test.txt" in workflow
        prerequisite = job_steps["Verify required test inputs"]["run"]
        assert 'python -c "import folio.iri"' in prerequisite
        assert "test -f FOLIO.owl" in prerequisite
        assert "test -f FOLIO-webprotege-merge-output.owl" in prerequisite
        assert "python -m pytest tests -q -ra" in workflow


def test_tests_workflow_preserves_pr_and_main_push_triggers():
    workflow = yaml.safe_load(text(TESTS))
    triggers = workflow[True]  # PyYAML 1.1 parses the plain `on` key as true.
    assert triggers["pull_request"] is None
    assert triggers["push"]["branches"] == ["main"]
