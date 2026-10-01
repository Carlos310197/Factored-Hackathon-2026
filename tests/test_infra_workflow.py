from pathlib import Path

import yaml

WF = yaml.safe_load(Path(".github/workflows/infra.yml").read_text())
ON = WF.get("on", WF.get(True))  # PyYAML parses the bare key `on` as True


def test_triggers_are_scoped_to_platform():
    for event in ("pull_request", "push"):
        assert "infra/terraform/platform/**" in ON[event]["paths"]
    assert ON["push"]["branches"] == ["main"]


def test_workflow_apply_only_on_main():
    apply = WF["jobs"]["apply"]
    assert apply["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert "apply" not in " ".join(_runs("check"))


def test_oidc_permissions_and_no_secrets():
    assert WF["permissions"]["id-token"] == "write"
    assert "secrets." not in Path(".github/workflows/infra.yml").read_text()


def test_failed_plan_is_not_masked_by_tee():
    # explicit `shell: bash` makes GitHub use `-eo pipefail`; the default `bash -e` would hide a failing `plan | tee`
    assert WF["defaults"]["run"]["shell"] == "bash"


def _runs(job):
    return [str(s.get("run", "")) for s in WF["jobs"][job]["steps"]]


def test_no_plan_artifact_with_organizer_secret():
    # a saved plan file holds sensitive values in plaintext; never upload it
    text = Path(".github/workflows/infra.yml").read_text()
    assert "upload-artifact" not in text and "download-artifact" not in text


def test_pull_requests_get_no_cloud_credentials():
    # gha-deploy trusts main only; PR checks are fmt/validate/mocked tests
    job = WF["jobs"]["check"]
    assert job["if"] == "github.event_name == 'pull_request'"
    assert not any("configure-aws-credentials" in str(s.get("uses", "")) for s in job["steps"])
    assert "terraform test" in _runs("check") and "terraform init -backend=false -input=false" in _runs("check")
    assert "pull-requests" not in WF["permissions"]


def test_state_lock_waits_instead_of_failing():
    for job, verb in (("apply", "terraform apply"),):
        cmd = next(r for r in _runs(job) if r.startswith(verb))
        assert "-lock-timeout=5m" in cmd


def test_workflow_level_concurrency_serializes_main():
    assert WF["concurrency"] == {"group": "infra-${{ github.ref }}", "cancel-in-progress": False}


def test_smoke_test_runs_as_pipeline_runner():
    steps = WF["jobs"]["apply"]["steps"]
    smoke = next(i for i, s in enumerate(steps) if s.get("name") == "Smoke test")
    creds = [s for s in steps[:smoke] if "configure-aws-credentials" in str(s.get("uses", ""))]
    role = creds[-1]["with"]["role-to-assume"].removeprefix("${{ env.").removesuffix(" }}")
    assert WF["env"][role].endswith(":role/pipeline-runner")


def test_actions_pinned_to_commit_sha():
    # jobs hold admin OIDC credentials; a moved tag must not change the code that runs
    import re
    uses = re.findall(r"uses:\s*(\S+)", Path(".github/workflows/infra.yml").read_text())
    assert uses and all(re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u) for u in uses), uses
