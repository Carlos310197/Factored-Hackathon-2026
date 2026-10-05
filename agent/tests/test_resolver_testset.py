import csv
import json
from collections import Counter

import pytest

from bankagent.llm.config import load_models
from bankagent.resolver.histories import TransactionSource, sample_histories
from bankagent.resolver.records import country_of, load_jsonl, public, save_jsonl
from bankagent.resolver.simulate import load_sim_config
from bankagent.resolver.testset import (ingest_test_set, make_ceiling_sheet, make_test_sheet, read_ceiling,
                                        sha256_file, style_hint, write_sheet)
from tests.resolver_llm import ScriptedLLM

M = load_models(env={})
QUOTAS = {"hard": 6, "easy": 4, "nil": 2}


@pytest.fixture(scope="module")
def sheet(history_serving):
    hs = sample_histories(TransactionSource(history_serving), "test", 120, seed=3)
    return make_test_sheet(hs, load_sim_config(), seed=3, quotas=QUOTAS)


def fill(stem, message=lambda row: f"mensaje {row['case_id']}"):
    src = stem.with_suffix(".csv")
    rows = list(csv.DictReader(src.open(encoding="utf-8")))
    out = stem.parent / "completed.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        for r in rows:
            w.writerow(r | {"message": message(r)})
    return out


def test_sheet_meets_quotas_and_balances_languages(sheet):
    assert Counter(c["slice"] for c in sheet) == QUOTAS
    for k in QUOTAS:
        langs = Counter(c["lang"] for c in sheet if c["slice"] == k)
        assert abs(langs["es"] - langs["pt"]) <= 1
    for c in sheet:
        ids = [t["transaction_id"] for t in c["candidates"]]
        assert (c["target_id"] is None) == (c["slice"] == "nil")
        assert c["target"]["transaction_id"] not in ids if c["slice"] == "nil" else c["target_id"] in ids
    assert "CLI-" not in json.dumps(sheet)


def test_sheet_files_and_ingestion(sheet, tmp_path):
    stem = tmp_path / "test_sheet_v1"
    write_sheet(sheet, stem)
    header = next(csv.reader(stem.with_suffix(".csv").open(encoding="utf-8")))
    assert header == ["case_id", "lang", "instruction", "describe_this", "style_hint", "candidates", "message"]
    completed = fill(stem)
    rows, digest = ingest_test_set(stem, completed, ScriptedLLM(mentions={"merchant": "x"}), M)
    assert len(rows) == len(sheet) and digest == sha256_file(completed) and len(digest) == 64
    assert rows[0]["message"] == f"mensaje {rows[0]['case_id']}" and rows[0]["extraction"]["mentions"]["merchant"] == "x"
    assert "instruction" not in rows[0] and rows[0]["versions"]["extract"][1] == "extract.v2"


def test_ingestion_refuses_missing_messages_and_survives_extract_errors(sheet, tmp_path):
    stem = tmp_path / "s"
    write_sheet(sheet, stem)
    partial = fill(stem, message=lambda r: "" if r["case_id"] == sheet[0]["case_id"] else "hola")
    with pytest.raises(ValueError, match="no message"):
        ingest_test_set(stem, partial, ScriptedLLM(), M)
    rows, _ = ingest_test_set(stem, fill(stem), ScriptedLLM(fail_every=2), M)
    failed = [r for r in rows if "error" in r["extraction"]]
    assert failed and all(r["extraction"]["mentions"] == {} for r in failed)


def test_ceiling_round_trip(sheet, tmp_path):
    rows = [c | {"message": "m"} for c in sheet]
    ids = make_ceiling_sheet(rows, 5, seed=1, path=tmp_path / "ceiling.csv")
    lines = list(csv.DictReader((tmp_path / "ceiling.csv").open(encoding="utf-8")))
    assert [r["case_id"] for r in lines] == ids and "target" not in lines[0]
    with (tmp_path / "ceiling.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=lines[0].keys())
        w.writeheader()
        for i, r in enumerate(lines):
            w.writerow(r | {"pick": "none" if i == 0 else "1"})
    picks = read_ceiling(tmp_path / "ceiling.csv", rows)
    by_id = {r["case_id"]: r for r in rows}
    assert picks[ids[0]] is None and picks[ids[1]] == by_id[ids[1]]["candidates"][0]["transaction_id"]


def test_style_hint_text():
    s = {"no_detail": False, "merchant": "absent", "amount": "approx", "date": "relative", "date_label": "last week",
         "type_hint": "present", "channel_hint": "absent", "city": "n/a"}
    assert style_hint(s) == ("don't name the merchant; say roughly how much; say when loosely ('last week'); "
                             "say what kind of transaction it was")


def test_records_helpers(tmp_path):
    t = {"transaction_id": "TRX-1", "customer_id": "CLI-1", "product_id": "PRD-1", "transaction_country": "Colombia"}
    assert public(t) == {"transaction_id": "TRX-1", "transaction_country": "Colombia"}
    assert country_of([t, t | {"transaction_country": "Perú"}, t]) == "Colombia" and country_of([]) is None
    rows = [{"a": 1, "b": "ñ"}, {"a": None}]
    save_jsonl(rows, tmp_path / "x" / "rows.jsonl")
    assert load_jsonl(tmp_path / "x" / "rows.jsonl") == rows


def test_ingestion_reads_a_sheet_saved_by_spanish_excel(sheet, tmp_path):
    """Excel in a Spanish locale saves CSV with ';' and a byte-order mark."""
    stem = tmp_path / "s"
    write_sheet(sheet, stem)
    rows = list(csv.DictReader(stem.with_suffix(".csv").open(encoding="utf-8")))
    excel = tmp_path / "excel.csv"
    with excel.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow(r | {"message": "me cobraron dos veces; ¿qué pasó?"})
    ingested, _ = ingest_test_set(stem, excel, ScriptedLLM(), M)
    assert len(ingested) == len(sheet) and ingested[0]["message"] == "me cobraron dos veces; ¿qué pasó?"
