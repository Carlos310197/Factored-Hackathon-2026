"""Tag each demo identity with the /demo scenarios its real (synthetic) data supports (UI spec §4.9, §9.3).
Never fabricates: a scenario no customer supports is printed as MISSING.
Usage: uv run python scripts/tag_scenarios.py data/serving config/demo_users.yaml"""
import json
import re
import sys
from pathlib import Path

import duckdb
import yaml

from bankagent.identity.users import hash_password

SCENARIOS = ("account_inquiry", "decline_explanation", "dispute_filed", "clarify", "abstain",
             "unauthorized_handoff", "injection_refused", "expired_token")
WINDOW_DAYS = 60


def customer_facts(root: Path) -> dict[str, dict]:
    root = Path(root)
    run_id = json.loads((root / "latest.json").read_text())["run_id"]
    glob = str(root / run_id / "fct_transaction" / "*.parquet")
    con = duckdb.connect()
    rows = con.execute(f"""
        WITH t AS (SELECT * FROM read_parquet('{glob}')),
             w AS (SELECT * FROM t WHERE process_date > (SELECT max(process_date) FROM t) - INTERVAL {WINDOW_DAYS} DAY)
        SELECT customer_id,
               count(*) AS in_window,
               bool_or(transaction_status = 'Declined') AS declined,
               bool_or(transaction_status = 'Approved') AS approved,
               bool_or(transaction_status = 'Approved' AND transaction_type = 'Purchase'
                       AND coalesce(amount_usd, CASE WHEN currency = 'USD' THEN amount END, 1e9) <= 500
                       AND coalesce(fraud_score, 0) <= 30 AND NOT coalesce(is_fraud, false)) AS eligible_dispute,
               max(dups) > 1 AS duplicate_pair
        FROM (SELECT *, count(*) OVER (PARTITION BY customer_id, merchant_name, amount, process_date) AS dups FROM w)
        GROUP BY customer_id""").fetchall()
    cols = ("in_window", "declined", "approved", "eligible_dispute", "duplicate_pair")
    return {r[0]: dict(zip(cols, r[1:])) for r in rows}


def _qualifies(scenario: str, f: dict) -> bool:
    if not f or not f.get("in_window"):
        return False
    if scenario == "decline_explanation":
        return bool(f["declined"])
    if scenario == "dispute_filed":
        return bool(f["eligible_dispute"])
    if scenario == "unauthorized_handoff":
        return bool(f["approved"])
    return True


def _rank(scenario: str, u: dict, f: dict) -> tuple:
    prefer_pt = scenario == "decline_explanation" and u.get("lang") == "pt"
    prefer_dup = scenario == "dispute_filed" and bool(f.get("duplicate_pair"))
    return (not prefer_pt, not prefer_dup, len(u["scenarios"]))  # then the least-loaded identity


def assign(users: list[dict], facts: dict[str, dict]) -> tuple[list[dict], list[str]]:
    out = [dict(u) for u in users]
    customers = [u for u in out if u.get("role", "customer") == "customer" and u.get("customer_id")]
    for u in customers:
        u["scenarios"], u["short_ttl_allowed"] = [], False
    missing = []
    for s in SCENARIOS:
        pool = [u for u in customers if _qualifies(s, facts.get(u["customer_id"], {}))]
        if not pool:
            missing.append(s)
            continue
        pick = sorted(pool, key=lambda u: _rank(s, u, facts[u["customer_id"]]))[0]
        pick["scenarios"].append(s)
        if s == "expired_token":
            pick["short_ttl_allowed"] = True
    return out, missing


STAFF = (("agent.ana", "Ana R. (agente de prueba)", "es"), ("agent.luis", "Luis M. (agente de prueba)", "es"),
         ("agent.bia", "Bia S. (agente de teste)", "pt"))


def add_demo_passwords_and_staff(users: list[dict]) -> list[dict]:
    """Idempotent. demoNN customers get the picker's demo-NN password; staff get staff-<name>-demo (demo-only)."""
    out = [dict(u) for u in users]
    for u in out:
        m = re.fullmatch(r"demo(\d+)", u["username"])
        if m and "demo_password" not in u:  # ponytail: other usernames (hand-added) keep whatever they have
            u["demo_password"] = f"demo-{m[1]}"
    have = {u["username"] for u in out}
    for username, name, _ in STAFF:
        if username not in have:
            pw = f"staff-{username.split('.')[1]}-demo"
            out.append({"username": username, "password_sha256": hash_password(pw), "role": "agent",
                        "display_name": name, "demo_password": pw})
    return out


def main(serving: str, users_path: str) -> None:
    doc = yaml.safe_load(Path(users_path).read_text(encoding="utf-8"))
    users, missing = assign(add_demo_passwords_and_staff(doc["users"]), customer_facts(Path(serving)))
    doc["users"] = users
    Path(users_path).write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    for s in SCENARIOS:
        who = [u["username"] for u in users if s in u.get("scenarios", [])]
        print(f"{s:22} {who[0] if who else 'MISSING'}")
    if missing:
        print(f"MISSING: {', '.join(missing)} (no customer's data supports them; nothing was invented)", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
