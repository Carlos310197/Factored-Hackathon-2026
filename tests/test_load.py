from pipeline.load import StageFile, LoadAction, plan_loads, relative_path, chunks, TABLES

def sf(path, md5="a", size=10):
    return StageFile(path=path, md5=md5, size=size)

def test_plan_loads_new_restated_skipped():
    files = [sf("transactions/year=2026/month=06/day=17/transactions_20260617.csv", "m1"),
             sf("transactions/year=2026/month=06/day=18/transactions_20260618.csv", "m2"),
             sf("transactions/year=2026/month=06/day=19/transactions_20260619.csv", "m3")]
    manifest = {"transactions/year=2026/month=06/day=17/transactions_20260617.csv": "m1",
                "transactions/year=2026/month=06/day=18/transactions_20260618.csv": "OLD"}
    actions = plan_loads(files, manifest)
    assert actions == [
        LoadAction(files[0].path, "skipped"),
        LoadAction(files[1].path, "restated"),
        LoadAction(files[2].path, "new"),
    ]

def test_plan_loads_zero_row_file_is_new():
    assert plan_loads([sf("transactions/x.csv", "m", size=0)], {}) == [LoadAction("transactions/x.csv", "new")]

def test_relative_path_strips_stage_prefix():
    name = "s3://bucket/data/transactions/year=2026/month=06/day=17/transactions_20260617.csv"
    assert relative_path("s3://bucket/data/", name) == "transactions/year=2026/month=06/day=17/transactions_20260617.csv"

def test_relative_path_internal_stage_strips_stage_name():
    assert relative_path("", "fixture_stage/transactions/year=2026/month=06/day=17/transactions_20260617.csv") == \
        "transactions/year=2026/month=06/day=17/transactions_20260617.csv"

def test_chunks():
    assert list(chunks([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]

def test_tables_registry():
    assert TABLES["INTERACTIONS"] == "call_center_interactions/"
    assert TABLES["CUSTOMERS"] == "customers.csv"
