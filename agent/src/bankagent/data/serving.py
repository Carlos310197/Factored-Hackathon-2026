import json
import re
import threading
from dataclasses import dataclass
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import duckdb

from bankagent.data.contract import CONTRACT, contract_hash

log = logging.getLogger(__name__)
STALE_AFTER = timedelta(days=2)

RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class ServingError(Exception):
    pass


@dataclass(frozen=True)
class Pointer:
    run_id: str
    max_process_date: date
    exported_at: str


def _jsonable(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


class ServingData:
    def __init__(self, base_uri: str, region: str = "us-east-1"):
        self.base = base_uri.rstrip("/")
        self.region = region
        self._con = duckdb.connect(":memory:")
        self._lock = threading.Lock()
        if self.base.startswith("s3://"):
            self._con.execute("INSTALL httpfs; LOAD httpfs; INSTALL aws; LOAD aws;")
            self._con.execute(f"CREATE SECRET serving_s3 (TYPE s3, PROVIDER credential_chain, REGION '{region}')")

    def _read_text(self, uri: str) -> str:
        if uri.startswith("s3://"):
            import boto3
            bucket, key = uri[5:].split("/", 1)
            return boto3.client("s3", region_name=self.region).get_object(Bucket=bucket, Key=key)["Body"].read().decode()
        with open(uri, encoding="utf-8") as f:
            return f.read()

    def pointer(self) -> Pointer:
        try:
            p = json.loads(self._read_text(f"{self.base}/latest.json"))
            pointer = Pointer(p["run_id"], date.fromisoformat(p["max_process_date"]), p.get("exported_at", ""))
        except Exception as e:
            raise ServingError(f"cannot read serving pointer: {e}") from e
        # A pointer must name our columns or the parquet would be misread; only old local dev builds omit them.
        legacy_dev = "contract_hash" not in p and str(p.get("source", "")).startswith("local_build")
        if not legacy_dev and p.get("contract_hash") != contract_hash():
            raise ServingError(f"serving contract mismatch for run {pointer.run_id}")
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(pointer.exported_at.replace("Z", "+00:00"))
            if age > STALE_AFTER:
                log.warning("serving pointer is stale", extra={"run_id": pointer.run_id, "age_h": round(age.total_seconds() / 3600)})
        except ValueError:
            log.warning("serving pointer is stale", extra={"run_id": pointer.run_id, "exported_at": pointer.exported_at})
        return pointer

    def query(self, run_id: str, table: str, where: str, params: list, order_by: str = "") -> list[dict]:
        if table not in CONTRACT:
            raise ValueError(f"unknown table: {table}")
        if not RUN_ID_RE.match(run_id):
            raise ValueError(f"unsafe run_id: {run_id!r}")
        sql = f"select * from read_parquet('{self.base}/{run_id}/{table}/*.parquet') where {where}"
        if order_by:
            sql += f" order by {order_by}"
        try:
            with self._lock:
                cur = self._con.execute(sql, params)
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
        except duckdb.Error as e:
            raise ServingError(str(e)) from e
        return [{c: _jsonable(v) for c, v in zip(cols, r)} for r in rows]
