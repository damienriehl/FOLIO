"""Execute workflow Bash with a closed, recorded external-command boundary.

These tests exercise orchestration, not GitHub's event delivery or action code.
Only explicitly queued fake commands can run; jq evaluates real API fixtures.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github/workflows"
REPO = "example/FOLIO"
C = "c" * 40
B = "b" * 40
S = "a" * 40
PR = f"repos/{REPO}/pulls/7"
CORRECTION_FILES = {
    "correction-source.owl": "source bytes\n",
    "corrected.owl": "candidate bytes\n",
    "correction-ledger.json": "{\"ledger\": []}\n",
    "correction-evidence.json": "{\"evidence\": []}\n",
}


def workflow_steps(filename, job):
    return yaml.safe_load((WORKFLOWS / filename).read_text())["jobs"][job]["steps"]


QA_STEPS = workflow_steps("ontology-hydration-qa.yml", "trusted-model-review")
TRIGGER_STEPS = workflow_steps("ontology-hydration-qa-trigger.yml", "dispatch-trusted-review")


class ShellBoundary:
    def __init__(self, root):
        self.root = root
        self.queue = []
        self.values = {
            "github.event.workflow_run.head_sha": C,
            "github.event.repository.default_branch": "main",
            "inputs.correction_run_id": "42",
            "inputs.correction_source_sha": S,
        }
        self.env = {
            "PATH": str(root / "bin"), "HOME": str(root), "LC_ALL": "C",
            "GITHUB_REPOSITORY": REPO, "REVIEWED_SHA": C, "BASELINE_SHA": B,
            "CANDIDATE_REPOSITORY": REPO, "PULL_REQUEST_NUMBER": "7",
            "RUN_ID": "99", "GITHUB_OUTPUT": str(root / "outputs"),
            "JOB_STATUS": "success", "BOUNDARY_ROOT": str(root),
        }
        (root / "bin").mkdir()
        (root / "inputs").mkdir()
        (root / "evidence").mkdir()
        (root / "inputs/candidate.owl").write_text(CORRECTION_FILES["corrected.owl"])
        (root / "inputs/baseline.owl").write_text("baseline bytes\n")
        self.pr = {"head": {"sha": C, "ref": "canary", "repo": {"full_name": REPO}},
                   "base": {"sha": B}}
        (root / "inputs/pr.json").write_text(json.dumps(self.pr))
        (root / "evidence/report.json").write_text(json.dumps({
            "candidate_hash": hashlib.sha256((root / "inputs/candidate.owl").read_bytes()).hexdigest()
        }))
        # No inherited PATH: an unrecognized network/model command cannot fall back
        # to a real executable. A missing prerequisite fails rather than skips.
        for command in ("bash", "jq", "sha256sum", "cut", "cp", "mv", "mkdir", "tar", "date"):
            executable = shutil.which(command)
            assert executable, f"workflow test requires {command}"
            (root / "bin" / command).symlink_to(executable)
        fake = root / "fake-command"
        fake.write_text(f"#!{sys.executable}\n" + '''
import json, os, pathlib, subprocess, sys
root = pathlib.Path(os.environ["BOUNDARY_ROOT"])
args = [pathlib.Path(sys.argv[0]).name, *sys.argv[1:]]
with (root / "commands.jsonl").open("a") as log:
    log.write(json.dumps(args) + "\\n")
queue = json.loads((root / "queue.json").read_text())
if not queue or queue[0]["args"] != args:
    (root / "unexpected").write_text(json.dumps({"actual": args, "remaining": queue}))
    sys.exit(91)
reply = queue.pop(0)
(root / "queue.json").write_text(json.dumps(queue))
for name, data in reply.get("files", {}).items():
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data)
if "pages" in reply:
    for page in reply["pages"]:
        if "--jq" in args:
            query = args[args.index("--jq") + 1]
            result = subprocess.run(["jq", "-r", query], input=json.dumps(page), text=True, capture_output=True)
            if result.returncode:
                sys.stderr.write(result.stderr)
                sys.exit(result.returncode)
            sys.stdout.write(result.stdout)
        else:
            print(json.dumps(page))
else:
    sys.stdout.write(reply.get("stdout", ""))
sys.exit(reply.get("status", 0))
''')
        fake.chmod(0o755)
        for command in ("gh", "git", "python", "oras"):
            (root / "bin" / command).symlink_to(fake)

    def expect(self, args, **reply):
        self.queue.append({"args": args, **reply})

    def api(self, endpoint, payload, query=None, paginate=False, status=0):
        args = ["gh", "api"] + (["--paginate"] if paginate else []) + [endpoint]
        if query:
            args += ["--jq", query]
        self.expect(args, pages=payload if paginate else [payload], status=status)

    def run(self, name, steps=QA_STEPS):
        step = next(step for step in steps if step.get("name") == name)
        script = re.sub(r"\$\{\{\s*(.*?)\s*\}\}", lambda m: self.values[m[1]], step["run"])
        (self.root / "queue.json").write_text(json.dumps(self.queue))
        result = subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
                                env=self.env, cwd=self.root, text=True, capture_output=True, timeout=10)
        assert not (self.root / "unexpected").exists(), (self.root / "unexpected").read_text() if (self.root / "unexpected").exists() else ""
        self.queue = json.loads((self.root / "queue.json").read_text())
        return result

    def outputs(self):
        return dict(line.split("=", 1) for line in (self.root / "outputs").read_text().splitlines())

    def commands(self):
        return [json.loads(line) for line in (self.root / "commands.jsonl").read_text().splitlines()]


@pytest.fixture
def shell(tmp_path):
    return ShellBoundary(tmp_path)


def resolve_trigger(shell, *, changed=True, missing_artifact=False, api_failure=False):
    shell.api(f"repos/{REPO}/actions/runs/99", {"pull_requests": [{"number": 7}]},
              ".pull_requests[0].number // empty")
    shell.api(PR, shell.pr, status=1 if api_failure else 0)
    if api_failure or shell.pr["head"]["sha"] != C:
        return
    shell.api(PR + "/files", [[{"filename": "README.md"}],
                             [{"filename": "FOLIO.owl" if changed else "AGENTS.md"}]],
              '.[] | select(.filename == "FOLIO.owl") | .filename', paginate=True)
    if changed:
        shell.api(f"repos/{REPO}/commits/{C}", {
            "commit": {"message": "fix(ontology): apply verified QA corrections"},
            "parents": [{"sha": S}]})
        artifacts = [] if missing_artifact else [
            {"expired": False, "created_at": "2026-10-24", "workflow_run": {"id": 41}},
            {"expired": False, "created_at": "2026-10-25", "workflow_run": {"id": 42}},
            {"expired": True, "created_at": "2026-10-26", "workflow_run": {"id": 43}},
        ]
        shell.api(f"repos/{REPO}/actions/artifacts?name=ontology-correction-{S}", {"artifacts": artifacts},
                  '.artifacts | map(select(.expired == false)) | max_by(.created_at) | .workflow_run.id // empty')


def test_trigger_discovers_lineage_on_later_files_page_and_dispatches_exact_endpoints(shell):
    resolve_trigger(shell)
    result = shell.run("Resolve immutable pull-request endpoints", TRIGGER_STEPS)
    assert result.returncode == 0, result.stderr
    assert shell.outputs() == {
        "ontology_changed": "true", "correction_commit": "true", "correction_run_id": "42",
        "correction_source_sha": S, "pull_request_number": "7", "reviewed_sha": C,
        "baseline_sha": B, "candidate_repository": REPO,
    }
    shell.values.update({f"steps.endpoints.outputs.{key}": value for key, value in shell.outputs().items()})
    shell.expect(["gh", "workflow", "run", "ontology-hydration-qa.yml", "--repo", REPO, "--ref", "main",
                  "-f", "pull_request_number=7", "-f", f"reviewed_sha={C}", "-f", f"baseline_sha={B}",
                  "-f", f"candidate_repository={REPO}", "-f", "correction_run_id=42",
                  "-f", f"correction_source_sha={S}"])
    assert shell.run("Dispatch protected model-bearing workflow", TRIGGER_STEPS).returncode == 0
    assert not shell.queue


def test_unrelated_files_do_not_request_dispatch(shell):
    resolve_trigger(shell, changed=False)
    assert shell.run("Resolve immutable pull-request endpoints", TRIGGER_STEPS).returncode == 0
    assert shell.outputs()["ontology_changed"] == "false"
    assert not shell.queue


@pytest.mark.parametrize("failure", ["moved_head", "missing_artifact", "api_failure"])
def test_trigger_fails_closed(shell, failure):
    if failure == "moved_head":
        shell.pr["head"]["sha"] = B
    resolve_trigger(shell, missing_artifact=failure == "missing_artifact", api_failure=failure == "api_failure")
    assert shell.run("Resolve immutable pull-request endpoints", TRIGGER_STEPS).returncode != 0
    assert not (shell.root / "outputs").exists()
    assert not shell.queue


def restore_lineage(shell, *, invalid=None, missing=None):
    metadata = {"path": ".github/workflows/ontology-hydration-qa.yml",
                "event": "workflow_dispatch", "head_branch": "main"}
    if invalid in metadata:
        metadata[invalid] = "untrusted"
    shell.api(f"repos/{REPO}/actions/runs/42", metadata)
    if invalid in metadata:
        return
    shell.api(f"repos/{REPO}/commits/{C}", {"parents": [{"sha": B if invalid == "parent" else S}]},
              ".parents[0].sha")
    if invalid == "parent":
        return
    files = {f"inputs/{name}": data for name, data in CORRECTION_FILES.items() if name != missing}
    if invalid == "bytes":
        files["inputs/corrected.owl"] = "wrong bytes\n"
    shell.expect(["gh", "run", "download", "42", "--repo", REPO, "--name", f"ontology-correction-{S}",
                  "--dir", "inputs"], files=files)


def queue_model(shell, correction=False):
    shell.expect(["python", "trusted-runner/scripts/detect_confirmed_debt_closure.py",
                  "--baseline", "inputs/baseline.owl", "--candidate", "inputs/candidate.owl",
                  "--debt", "trusted-runner/qa/ontology/confirmed-defects.json"], stdout='{"closed_count": 0}\n')
    args = ["python", "trusted-runner/scripts/run_trusted_ontology_qa.py", "--baseline", "inputs/baseline.owl",
            "--candidate", "inputs/candidate.owl", "--reviewed-sha", shell.env["REVIEWED_SHA"],
            "--bundle", "evidence", "--cache", ".ontology-qa-cache",
            "--corrected-output", "inputs/generated-correction/corrected.owl",
            "--generated-correction-ledger", "inputs/generated-correction/correction-ledger.json",
            "--generated-correction-evidence", "inputs/generated-correction/correction-evidence.json"]
    if shell.values["inputs.correction_run_id"]:
        args += ["--correction-source", "inputs/correction-source.owl", "--correction-ledger",
                 "inputs/correction-ledger.json", "--correction-evidence", "inputs/correction-evidence.json"]
    files = {f"inputs/generated-correction/{name}": data for name, data in CORRECTION_FILES.items()
             if name != "correction-source.owl"} if correction else {}
    shell.expect(args, files=files, status=2 if correction else 0)


def test_restoration_preserves_exact_files_and_runner_arguments(shell):
    original = (shell.root / "inputs/candidate.owl").read_bytes()
    restore_lineage(shell)
    assert shell.run("Restore prior changed-record correction lineage").returncode == 0
    queue_model(shell)
    assert shell.run("Run trusted model QA").returncode == 0
    assert shell.outputs()["correction_ready"] == "false"
    assert (shell.root / "inputs/candidate.owl").read_bytes() == original
    for name, data in CORRECTION_FILES.items():
        assert (shell.root / "inputs" / name).read_text() == data
    assert not shell.queue


@pytest.mark.parametrize("invalid", ["path", "event", "head_branch", "parent", "bytes"])
def test_restoration_rejects_wrong_provenance_or_bytes_before_model_execution(shell, invalid):
    restore_lineage(shell, invalid=invalid)
    assert shell.run("Restore prior changed-record correction lineage").returncode != 0
    assert not shell.queue
    assert not any(command[0] == "python" for command in shell.commands())


def check_args(conclusion, sha=C):
    return ["gh", "api", "--method", "POST", f"repos/{REPO}/check-runs", "-f", "name=ontology-hydration-qa",
            "-f", f"head_sha={sha}", "-f", "status=completed", "-f", f"conclusion={conclusion}"]


def test_correction_fails_old_sha_before_push_and_keeps_acceptance_disabled(shell):
    shell.env["REVIEWED_SHA"] = S
    shell.values["inputs.correction_run_id"] = ""
    (shell.root / "inputs/candidate.owl").write_text("source bytes\n")
    (shell.root / "candidate-checkout").mkdir()
    queue_model(shell, correction=True)
    assert shell.run("Run trusted model QA").returncode == 0
    assert shell.outputs()["correction_ready"] == "true"
    assert (shell.root / "inputs/correction-source.owl").read_text() == "source bytes\n"
    shell.api(PR, {"head": {"sha": S}}, ".head.sha")
    shell.expect(["git", "-C", "candidate-checkout", "add", "FOLIO.owl"])
    shell.expect(["git", "-C", "candidate-checkout", "-c", "user.name=github-actions", "-c",
                  "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit", "-m",
                  "fix(ontology): apply verified QA corrections"])
    shell.expect(check_args("failure", S))
    shell.expect(["git", "-C", "candidate-checkout", "push", "origin", "HEAD:canary"])
    assert shell.run("Commit verified ontology bytes for fresh review").returncode == 0
    assert not shell.queue
    assert (shell.root / "candidate-checkout/FOLIO.owl").read_text() == CORRECTION_FILES["corrected.owl"]
    names = [step.get("name") for step in QA_STEPS]
    assert names.index("Upload verified correction lineage") < names.index("Commit verified ontology bytes for fresh review")
    # Contract tests separately pin each guard. Also ensure every acceptance
    # action remains ineligible on the correction-producing execution path.
    for step in QA_STEPS:
        if step.get("uses") == "actions/attest@v4" or "oras push" in step.get("run", "") or step.get("name") == "Publish stable required check":
            assert "steps.qa.outputs.correction_ready != 'true'" in step["if"]
