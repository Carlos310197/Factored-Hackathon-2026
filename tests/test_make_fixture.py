import csv
from pathlib import Path
from fixtures.make_fixture import write_phase, COLUMNS

def rows(p): return list(csv.DictReader(open(p, newline="", encoding="utf-8")))

def test_phase1_and_phase2_shapes(tmp_path):
    p1 = write_phase(tmp_path / "p1", 1)
    assert [p.name for p in p1] == ["transactions_20260617.csv"]
    r17 = rows(p1[0]); assert len(r17) == 20 and list(r17[0].keys()) == COLUMNS
    p2 = write_phase(tmp_path / "p2", 2)
    by = {p.name: p for p in p2}
    r17b = rows(by["transactions_20260617.csv"])
    assert len(r17b) == 24 and len({r["transaction_id"] for r in r17b if r["transaction_status"] == "Reversed"}) == 3
    ids = [r["transaction_id"] for r in r17b]; assert len(ids) - len(set(ids)) == 5
    assert len(rows(by["transactions_20260618.csv"])) == 10
    assert "merchant_country" in rows(by["transactions_20260619.csv"])[0]
    assert any(r["amount"] == "N/A" for r in rows(by["transactions_20260620.csv"]))
    assert rows(by["transactions_20260621.csv"]) == []


def test_phase3_dimensions_and_phase4_orphan(tmp_path):
    cust, prod = write_phase(tmp_path / "p3", 3)
    assert [p.name for p in (cust, prod)] == ["customers.csv", "products.csv"] and cust.parent == tmp_path / "p3"
    (c,), (p,) = rows(cust), rows(prod)
    assert c["customer_id"] == p["customer_id"] == "CUS-FIXTURE0001" and p["product_id"] == "PRD-FIXTURE0001"
    (d22,) = write_phase(tmp_path / "p4", 4)
    r = rows(d22)
    assert d22.name == "transactions_20260622.csv" and list(r[0].keys()) == COLUMNS
    assert [x["product_id"] for x in r] == ["PRD-FIXTURE0001", "PRD-ORPHAN0001"]
