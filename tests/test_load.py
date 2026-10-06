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


class FakeCur:
    """COPY returns one row per file; the 2nd COPY fails; INSERTs into the manifest are captured."""
    def __init__(self, fail_on_copy=2, listing=()):
        self.copies, self.fail_on_copy, self.manifest, self.listing = 0, fail_on_copy, [], list(listing)
        self._last = []
    def execute(self, sql, params=None):
        low = sql.lower()
        if low.startswith("list"):
            self._last = self.listing
        elif low.startswith("select file_path"):
            self._last = []
        elif low.startswith("copy into"):
            self.copies += 1
            if self.copies == self.fail_on_copy:
                raise RuntimeError("batch failed")
            files = sql.split("files = (", 1)[1].split(")", 1)[0]
            self._last = [(f.strip(" '"), "LOADED", 1, 1) for f in files.split(",")]
        return self
    def fetchall(self): return self._last
    def executemany(self, sql, rows): self.manifest += rows


class FakeConn:
    def __init__(self, cur): self.cur, self.commits = cur, 0
    def cursor(self): return self.cur
    def commit(self): self.commits += 1


def test_partial_failure_records_completed_batches(monkeypatch):
    import pipeline.load as L
    monkeypatch.setattr(L, "FILES_PER_COPY", 2)
    listing = [(f"s3://b/data/transactions/t{i}.csv", 10, f"e{i}", "x") for i in range(4)]
    cur = FakeCur(fail_on_copy=2, listing=listing)
    import pytest
    with pytest.raises(RuntimeError):
        L.run_load(FakeConn(cur), "r1", "RAW.ORGANIZER_STAGE", "s3://b/data/", {"TRANSACTIONS": "transactions/"})
    # batch 1 (t0, t1) is in RAW (COPY autocommits), so it must be in the manifest too
    assert sorted(r[2] for r in cur.manifest) == ["transactions/t0.csv", "transactions/t1.csv"]


def test_copy_tolerates_zero_files_processed_row():
    from pipeline.load import copy_files
    class Cur(FakeCur):
        def execute(self, sql, params=None):
            self._last = [("Copy executed with 0 files processed.",)]
            return self
    assert copy_files(Cur(), "TRANSACTIONS", "RAW.ORGANIZER_STAGE", ["transactions/t0.csv"], force=False) == {"transactions/t0.csv": 0}


def test_copy_escapes_quotes_in_file_names():
    from pipeline.load import copy_files
    class Cur(FakeCur):
        def execute(self, sql, params=None):
            self.sql = sql
            self._last = []
            return self
    cur = Cur()
    copy_files(cur, "TRANSACTIONS", "RAW.ORGANIZER_STAGE", ["transactions/o'brien.csv"], force=False)
    assert "files = ('transactions/o''brien.csv')" in cur.sql


def test_rerun_over_same_drop_copies_nothing():
    """Re-run idempotency at the RAW boundary: same files + same ETags -> every file skipped, no COPY, no new manifest rows."""
    import pipeline.load as L

    class Cur(FakeCur):
        def execute(self, sql, params=None):
            if sql.lower().startswith("select file_path"):  # read_manifest: latest non-skipped row per file
                self._last = [(r[2], r[3]) for r in self.manifest if r[4] != "skipped"]
                return self
            return super().execute(sql, params)

    listing = [(f"s3://b/data/transactions/t{i}.csv", 10, f"e{i}", "x") for i in range(3)]
    cur = Cur(fail_on_copy=0, listing=listing)
    tables = {"TRANSACTIONS": "transactions/"}
    first = L.run_load(FakeConn(cur), "r1", "RAW.ORGANIZER_STAGE", "s3://b/data/", tables)
    copies, manifest = cur.copies, list(cur.manifest)
    second = L.run_load(FakeConn(cur), "r2", "RAW.ORGANIZER_STAGE", "s3://b/data/", tables)
    assert first["TRANSACTIONS"] == {"new": 3, "restated": 0, "skipped": 0}
    assert second["TRANSACTIONS"] == {"new": 0, "restated": 0, "skipped": 3}
    assert cur.copies == copies and cur.manifest == manifest
