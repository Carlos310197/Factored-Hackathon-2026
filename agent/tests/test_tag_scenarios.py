import json

import duckdb

from scripts.tag_scenarios import SCENARIOS, assign, customer_facts


def build_serving(root):
    run = root / "RUN1" / "fct_transaction"
    run.mkdir(parents=True)
    (root / "latest.json").write_text(json.dumps({"run_id": "RUN1"}))
    rows = [
        # customer, date, merchant, amount, currency, amount_usd, type, status, fraud_score, is_fraud
        ("CLI-A", "2026-06-03", "Exito", 184900, "COP", 46.2, "Purchase", "Approved", 12.0, False),
        ("CLI-A", "2026-06-03", "Exito", 184900, "COP", 46.2, "Purchase", "Approved", 11.0, False),
        ("CLI-B", "2026-06-10", "Loja", 90, "USD", None, "Purchase", "Declined", 5.0, False),
        ("CLI-C", "2026-06-02", "Amazon", 420, "USD", None, "Purchase", "Approved", 61.0, True),
        ("CLI-D", "2025-01-01", "Old", 10, "USD", None, "Purchase", "Approved", 1.0, False),
        ("CLI-D", "2026-06-17", "Tienda", 10, "USD", None, "Purchase", "Approved", 1.0, False),
    ]
    con = duckdb.connect()
    con.execute("CREATE TABLE t (customer_id VARCHAR, process_date DATE, merchant_name VARCHAR, amount DOUBLE, "
                "currency VARCHAR, amount_usd DOUBLE, transaction_type VARCHAR, transaction_status VARCHAR, "
                "fraud_score DOUBLE, is_fraud BOOLEAN)")
    con.executemany("INSERT INTO t VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.execute(f"COPY t TO '{run / 'part-0.parquet'}' (FORMAT PARQUET)")


def test_customer_facts_uses_the_60_day_window(tmp_path):
    build_serving(tmp_path)
    f = customer_facts(tmp_path)
    assert f["CLI-A"]["duplicate_pair"] and f["CLI-A"]["eligible_dispute"]
    assert f["CLI-B"]["declined"] and not f["CLI-B"]["eligible_dispute"]
    assert f["CLI-C"]["approved"] and not f["CLI-C"]["eligible_dispute"]
    assert f["CLI-D"]["in_window"] == 1


def test_assign_prefers_pt_for_decline_and_reports_missing(tmp_path):
    build_serving(tmp_path)
    users = [{"username": "a", "customer_id": "CLI-A", "lang": "es"},
             {"username": "b", "customer_id": "CLI-B", "lang": "pt"},
             {"username": "c", "customer_id": "CLI-C", "lang": "es"},
             {"username": "d", "customer_id": "CLI-D", "lang": "es"},
             {"username": "staff", "role": "agent"}]
    out, missing = assign(users, customer_facts(tmp_path))
    by = {u["username"]: u for u in out}
    assert "dispute_filed" in by["a"]["scenarios"] and "decline_explanation" in by["b"]["scenarios"]
    assert "unauthorized_handoff" in by["c"]["scenarios"]
    assert sum(u.get("short_ttl_allowed", False) for u in out) == 1
    assert "scenarios" not in by["staff"] and missing == []
    assert set().union(*(set(u.get("scenarios", [])) for u in out)) == set(SCENARIOS)


def test_assign_reports_missing_when_no_customer_qualifies():
    users = [{"username": "a", "customer_id": "CLI-X", "lang": "es"}]
    facts = {"CLI-X": {"in_window": 1, "declined": False, "approved": True, "eligible_dispute": False,
                       "duplicate_pair": False}}
    _, missing = assign(users, facts)
    assert missing == ["decline_explanation", "dispute_filed"]


def test_staff_and_passwords_are_added_once_and_hand_added_users_kept():
    from scripts.tag_scenarios import add_demo_passwords_and_staff
    users = [{"username": "demo01", "customer_id": "CLI-A"}, {"username": "demo21", "customer_id": "CLI-Z",
                                                              "demo_password": "x"}]
    once = add_demo_passwords_and_staff(users)
    assert once[0]["demo_password"] == "demo-01" and once[1]["demo_password"] == "x"
    staff = [u for u in once if u.get("role") == "agent"]
    assert [u["username"] for u in staff] == ["agent.ana", "agent.luis", "agent.bia"]
    from bankagent.identity.users import hash_password
    assert all(u["password_sha256"] == hash_password(u["demo_password"]) for u in staff)
    assert add_demo_passwords_and_staff(once) == once
