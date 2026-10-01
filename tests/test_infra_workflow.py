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
    plan_steps = " ".join(str(s.get("run", "")) for s in WF["jobs"]["plan"]["steps"])
    assert "apply" not in plan_steps


def test_workflow_has_concurrency_group():
    assert WF["jobs"]["apply"]["concurrency"] == {"group": "infra-apply", "cancel-in-progress": False}


def test_oidc_permissions_and_no_secrets():
    assert WF["permissions"]["id-token"] == "write"
    assert "secrets." not in Path(".github/workflows/infra.yml").read_text()


def test_failed_plan_is_not_masked_by_tee():
    # explicit `shell: bash` makes GitHub use `-eo pipefail`; the default `bash -e` would hide a failing `plan | tee`
    assert WF["defaults"]["run"]["shell"] == "bash"
