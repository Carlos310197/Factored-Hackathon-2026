import re
from pathlib import Path

import yaml

CI_TEXT = Path(".github/workflows/ci.yml").read_text()
PL_TEXT = Path(".github/workflows/pipeline.yml").read_text()
CI, PL = yaml.safe_load(CI_TEXT), yaml.safe_load(PL_TEXT)
on = lambda wf: wf.get("on", wf.get(True))  # PyYAML parses the bare key `on` as True


def test_no_stored_secrets_and_pinned_actions():
    for text in (CI_TEXT, PL_TEXT):
        assert "secrets." not in text and "PRIVATE_KEY" not in text
        uses = re.findall(r"uses:\s*(\S+)", text)
        assert uses and all(re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u) for u in uses), uses


def test_pull_requests_get_no_cloud_credentials():
    unit = CI["jobs"]["unit"]
    assert not any("configure-aws-credentials" in str(s.get("uses", "")) for s in unit["steps"])
    assert CI["jobs"]["fixture"]["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"


def test_snowflake_jobs_run_as_pipeline_runner_with_wif():
    for wf, job in ((CI, "fixture"), (PL, "run")):
        creds = [s for s in wf["jobs"][job]["steps"] if "configure-aws-credentials" in str(s.get("uses", ""))]
        assert creds[0]["with"]["role-to-assume"] == "arn:aws:iam::762197749808:role/pipeline-runner"
        env = {**wf.get("env", {}), **wf["jobs"][job].get("env", {})}
        assert env["SNOWFLAKE_WORKLOAD_IDENTITY_PROVIDER"] == "AWS" and env["SNOWFLAKE_USER"] == "PIPELINE_SVC"
    assert CI["jobs"]["fixture"]["env"]["DBT_FIXTURE_TARGET"] == "ci_fixture"


def test_pipeline_order_schedule_and_concurrency():
    runs = [s.get("run", "") for s in PL["jobs"]["run"]["steps"]]
    order = ["pipeline.setup 02_raw_tables.sql", "pipeline.load", "dbt source freshness", "dbt build", "pipeline.dq_results", "pipeline.export"]
    idx = [next(i for i, r in enumerate(runs) if key in r) for key in order]
    assert idx == sorted(idx), runs
    assert "--target ci" in next(r for r in runs if "dbt build" in r)
    assert on(PL)["schedule"] and "workflow_dispatch" in on(PL) and on(PL)["push"]["branches"] == ["main"]
    assert PL["concurrency"] == {"group": "pipeline", "cancel-in-progress": False}


def test_dq_results_and_failed_steps_are_not_masked():
    steps = PL["jobs"]["run"]["steps"]
    dq = next(s for s in steps if "pipeline.dq_results" in s.get("run", ""))
    # DQ evidence is written even when dbt build fails, but not when dbt never ran (the load error stays the visible failure)
    assert dq.get("if") == "always() && hashFiles('dbt/target/run_results.json') != ''"
    assert PL["defaults"]["run"]["shell"] == "bash"  # -eo pipefail
