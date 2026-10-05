"""The agent's serving contract is a hand-copied list: prove it equals what dbt builds and the export writes."""
import csv
import importlib.util
from pathlib import Path

import yaml

from pipeline.export import EXPORT_TABLES, contract_hash

ROOT = Path(__file__).resolve().parents[1]


def _agent_contract():
    spec = importlib.util.spec_from_file_location("agent_contract", ROOT / "agent/src/bankagent/data/contract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dbt_columns() -> dict[str, list[str]]:
    models = yaml.safe_load((ROOT / "dbt/models/curated/schema.yml").read_text())["models"]
    cols = {m["name"]: [c["name"] for c in m["columns"]] for m in models}
    with open(ROOT / "dbt/seeds/seed_decline_reason.csv", newline="", encoding="utf-8") as f:
        cols["seed_decline_reason"] = next(csv.reader(f))
    return cols


def test_agent_contract_matches_dbt_columns_in_order():
    agent, dbt = _agent_contract().CONTRACT, _dbt_columns()
    for table in EXPORT_TABLES:
        assert agent[table] == dbt[table], table
    assert set(agent) == set(EXPORT_TABLES)


def test_pipeline_and_agent_hash_the_contract_the_same_way():
    agent = _agent_contract()
    assert contract_hash(agent.CONTRACT) == agent.contract_hash()
