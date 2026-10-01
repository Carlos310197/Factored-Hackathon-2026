import os, uuid
import pytest
from pipeline.connect import get_connection
from pipeline.load import list_stage_files, read_manifest, copy_files, record_manifest

pytestmark = pytest.mark.snowflake
STAGE_URL = f"s3://{os.environ.get('DATA_BUCKET','')}/data/"

@pytest.fixture(scope="module")
def cur():
    with get_connection() as conn:
        yield conn.cursor()

def test_list_stage_files_returns_relative_paths(cur):
    files = list_stage_files(cur, "RAW.ORGANIZER_STAGE", "customers.csv", STAGE_URL)
    assert len(files) == 1 and files[0].path == "customers.csv" and files[0].md5  # S3 ETag; multipart files end in -<parts>

def test_copy_and_manifest_roundtrip_on_fixture_db(cur):
    cur.execute("use database LATAM_FIXTURE")
    cur.execute("truncate table if exists RAW.CUSTOMERS")
    cur.execute("delete from META.RUN_MANIFEST where table_name = 'CUSTOMERS'")
    # stage a tiny customers file into the internal fixture stage
    import tempfile, pathlib
    p = pathlib.Path(tempfile.mkdtemp()) / "customers.csv"
    p.write_text("customer_id,country,segment\nC1,MX,Retail\nC2,CO,Premium\n")
    cur.execute(f"put file://{p} @RAW.FIXTURE_STAGE auto_compress=false overwrite=true")
    rows = copy_files(cur, "CUSTOMERS", "RAW.FIXTURE_STAGE", ["customers.csv"], force=False)
    assert rows == {"customers.csv": 2}
    run_id = uuid.uuid4().hex[:8]
    record_manifest(cur, run_id, "CUSTOMERS", [("customers.csv", "etag1", "new", 2)])
    assert read_manifest(cur, "CUSTOMERS") == {"customers.csv": "etag1"}
    n = cur.execute("select count(*), max(_source_file), max(_loaded_at) is not null from RAW.CUSTOMERS").fetchone()
    assert n[0] == 2 and n[1].endswith("customers.csv") and n[2]
