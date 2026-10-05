import csv
import json

import duckdb

from bankagent.context import SCOPE_READ, SessionContext
from bankagent.data.contract import CONTRACT
from bankagent.data.demo_users import build_users, select_demo_customers
from bankagent.data.local_build import build_local_serving
from bankagent.data.serving import ServingData
from bankagent.tools.read import ReadTools
from tests.fixtures.serving_fixture import C1

HEADERS = {
    "customers": "customer_id,document_number,document_type,first_name,last_name,date_of_birth,gender,email,mobile_phone,landline_phone,address,city,state,country,postal_code,detected_accent,segment,credit_score,estimated_monthly_income,occupation,marital_status,education_level,registration_date,registration_branch_id,customer_status,last_updated,accepts_marketing",
    "products": "product_id,customer_id,product_type,product_number,currency,current_balance,credit_limit,interest_rate,opening_date,expiration_date,opening_branch_id,product_status,opening_channel,has_linked_app,days_past_due,last_transaction_date,last_updated",
    "transactions": "transaction_id,transaction_date,process_date,product_id,customer_id,transaction_type,transaction_category,amount,currency,amount_usd,channel,branch_id,merchant_name,merchant_category,transaction_country,transaction_city,transaction_status,response_code,is_fraud,fraud_score,latitude,longitude",
    "complaints": "complaint_id,creation_date,process_date,customer_id,case_type,category,subcategory,reception_channel,affected_product_id,related_branch_id,origin_interaction_id,description,claimed_amount,currency,priority,status,assigned_agent_id,assignment_date,first_response_date,resolution_date,closing_date,sla_breached,resolution_days,resolution,compensation_granted,resolution_satisfaction,is_repeat_complainer",
}


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = header.split(",")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\ufeff")  # the organizer CSVs carry a UTF-8 BOM
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def raw_tree(root):
    write_csv(root / "customers.csv", HEADERS["customers"], [
        {"customer_id": "CLI-AAAAAAAAAAAA", "first_name": "Ana", "email": "ana@x.com", "document_number": "123",
         "city": "CDMX", "country": "México", "segment": "Retail", "registration_date": "2024-01-10",
         "customer_status": "Active", "last_updated": "2026-06-01 00:00:00", "accepts_marketing": "True"}])
    write_csv(root / "products.csv", HEADERS["products"], [
        {"product_id": "PRD-AAAAAAAAAAAA", "customer_id": "CLI-AAAAAAAAAAAA", "product_type": "Tarjeta de Crédito",
         "product_number": "4332181960", "currency": "USD", "current_balance": "1250.40", "credit_limit": "5000",
         "interest_rate": "0.42", "opening_date": "2024-01-10", "product_status": "Active", "has_linked_app": "True",
         "days_past_due": "", "last_transaction_date": "2026-06-10", "last_updated": "2026-06-10 00:00:00"}])
    day = root / "transactions" / "year=2026" / "month=06" / "day=10" / "transactions_20260610.csv"
    write_csv(day, HEADERS["transactions"], [
        {"transaction_id": "TRX-AAAAAAAAAAAAAAAAAAA1", "transaction_date": "2026-06-10 20:01:00",
         "process_date": "2026-06-10", "product_id": "PRD-AAAAAAAAAAAA", "customer_id": "CLI-AAAAAAAAAAAA",
         "transaction_type": "Purchase", "amount": "15.99", "currency": "USD", "amount_usd": "", "channel": "Web",
         "merchant_name": "Netflix", "transaction_country": "México", "transaction_status": "Approved",
         "response_code": "00", "is_fraud": "False", "fraud_score": "12.5"},
        {"transaction_id": "TRX-AAAAAAAAAAAAAAAAAAA2", "transaction_date": "2026-06-10 21:00:00",
         "process_date": "2026-06-10", "product_id": "PRD-AAAAAAAAAAAA", "customer_id": "CLI-AAAAAAAAAAAA",
         "transaction_type": "Purchase", "amount": "45000", "currency": "COP", "amount_usd": "11.25", "channel": "App",
         "merchant_name": "Rappi", "transaction_country": "Colombia", "transaction_status": "Declined",
         "response_code": "51", "is_fraud": "False", "fraud_score": "7"}])
    cday = root / "complaints" / "year=2026" / "month=06" / "day=10" / "complaints_20260610.csv"
    write_csv(cday, HEADERS["complaints"], [
        {"complaint_id": "CMP-AAAAAAAAAAAAAAAAAAA1", "creation_date": "2026-06-10 09:00:00",
         "process_date": "2026-06-10", "customer_id": "CLI-AAAAAAAAAAAA", "case_type": "Complaint",
         "category": "Transactions", "subcategory": "Cobro indebido", "reception_channel": "Call Center",
         "priority": "Medium", "status": "In Process", "sla_breached": "False", "resolution_satisfaction": "4.0",
         "is_repeat_complainer": "False", "description": "texto libre"}])


def test_local_build_follows_contract_and_drops_pii(tmp_path):
    raw_tree(tmp_path / "raw")
    pointer = build_local_serving(tmp_path / "raw", tmp_path / "out", run_id="local-test")
    assert pointer["run_id"] == "local-test" and pointer["max_process_date"] == "2026-06-10"
    assert json.loads((tmp_path / "out" / "latest.json").read_text())["run_id"] == "local-test"
    for table, cols in CONTRACT.items():
        got = duckdb.sql(f"describe select * from read_parquet('{tmp_path}/out/local-test/{table}/*.parquet')").fetchall()
        assert [r[0] for r in got] == cols, table


def test_local_build_values(tmp_path):
    raw_tree(tmp_path / "raw")
    build_local_serving(tmp_path / "raw", tmp_path / "out", run_id="local-test")
    sd = ServingData(str(tmp_path / "out"))
    ctx = SessionContext("CLI-AAAAAAAAAAAA", "S", frozenset({SCOPE_READ}), "es", 0)
    tools = ReadTools(sd)
    p = sd.pointer()
    txns = {x["transaction_id"]: x for x in tools.list_transactions(ctx, p.run_id, p.max_process_date).data}
    assert txns["TRX-AAAAAAAAAAAAAAAAAAA1"]["amount_usd"] == 15.99            # USD amount_usd filled from amount
    assert txns["TRX-AAAAAAAAAAAAAAAAAAA2"]["decline_reason_key"] == "insufficient_funds"
    assert tools.get_accounts(ctx, p.run_id, p.max_process_date).data[0]["product_last4"] == "1960"
    assert sd.query(p.run_id, "fct_complaint", "1=1", [])[0]["resolution_satisfaction"] == 4


def test_select_demo_customers_and_users(serving_root):
    picked = select_demo_customers(serving_root, {"México": 8, "Colombia": 6})
    assert picked == [{"customer_id": C1, "country": "México"}]  # C2 has no declined payment in the window
    users = build_users([{"customer_id": f"CLI-{i}", "country": "México"} for i in range(1, 9)], pt_every=4)
    assert [u["username"] for u in users][:2] == ["demo01", "demo02"]
    assert [u["lang"] for u in users].count("pt") == 2 and users[0]["otp"] == "123456"
    assert len(users[0]["password_sha256"]) == 64
