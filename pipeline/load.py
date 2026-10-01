"""Loader: LIST the organizer stage, compare ETags with META.RUN_MANIFEST, COPY new/changed files into RAW."""
from dataclasses import dataclass
from typing import Literal

TABLES: dict[str, str] = {
    "CUSTOMERS": "customers.csv",
    "PRODUCTS": "products.csv",
    "TRANSACTIONS": "transactions/",
    "COMPLAINTS": "complaints/",
    "INTERACTIONS": "call_center_interactions/",
}
Mode = Literal["new", "restated", "skipped"]


@dataclass(frozen=True)
class StageFile:
    path: str   # relative to the stage URL, e.g. transactions/year=2026/month=06/day=17/transactions_20260617.csv
    md5: str
    size: int


@dataclass(frozen=True)
class LoadAction:
    path: str
    mode: Mode


def relative_path(stage_url_prefix: str, listed_name: str) -> str:
    if stage_url_prefix and listed_name.startswith(stage_url_prefix):
        return listed_name[len(stage_url_prefix):]
    # internal stages (prefix '') list names as <stage_name>/<path>
    return listed_name.split("/", 1)[1] if "/" in listed_name else listed_name


def plan_loads(files: list[StageFile], manifest: dict[str, str]) -> list[LoadAction]:
    out = []
    for f in files:
        if f.path not in manifest:
            out.append(LoadAction(f.path, "new"))
        elif manifest[f.path] != f.md5:
            out.append(LoadAction(f.path, "restated"))
        else:
            out.append(LoadAction(f.path, "skipped"))
    return out


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield list(seq[i:i + n])


import argparse
import os
import sys
import uuid

FILES_PER_COPY = 500  # Snowflake FILES list limit is 1000

INCLUDE_METADATA = ("include_metadata = (_source_file = METADATA$FILENAME, _file_row = METADATA$FILE_ROW_NUMBER, "
                    "_file_last_modified = METADATA$FILE_LAST_MODIFIED, _loaded_at = METADATA$START_SCAN_TIME)")


def list_stage_files(cur, stage: str, prefix: str, stage_url_prefix: str) -> list[StageFile]:
    rows = cur.execute(f"list @{stage}/{prefix}").fetchall()  # name, size, md5, last_modified
    return [StageFile(relative_path(stage_url_prefix, r[0]), r[2], int(r[1])) for r in rows if r[0].endswith(".csv")]


def read_manifest(cur, table: str) -> dict[str, str]:
    rows = cur.execute(
        "select file_path, etag from META.RUN_MANIFEST where table_name = %s and mode <> 'skipped' "
        "qualify row_number() over (partition by file_path order by loaded_at desc) = 1", (table,)).fetchall()
    return {r[0]: r[1] for r in rows}


def copy_files(cur, table: str, stage: str, paths: list[str], force: bool) -> dict[str, int]:
    loaded: dict[str, int] = {}
    for batch in chunks(paths, FILES_PER_COPY):
        files = ", ".join(f"'{p}'" for p in batch)
        res = cur.execute(
            f"copy into RAW.{table} from @{stage} files = ({files}) "
            # named here, not on the stage: Terraform-managed stages carry no default format
            f"file_format = (format_name = 'RAW.CSV_HEADER') "
            f"match_by_column_name = case_insensitive {INCLUDE_METADATA} "
            f"on_error = abort_statement force = {'true' if force else 'false'}").fetchall()
        for r in res:  # file, status, rows_parsed, rows_loaded, ...
            listed = r[0]
            key = next((p for p in batch if listed.endswith(p)), listed)
            loaded[key] = int(r[3] or 0)
    for p in paths:
        loaded.setdefault(p, 0)  # header-only file or already-loaded file reports no row
    return loaded


def record_manifest(cur, run_id: str, table: str, rows: list[tuple[str, str, str, int]]) -> None:
    if rows:
        cur.executemany(
            "insert into META.RUN_MANIFEST (run_id, table_name, file_path, etag, mode, rows_loaded) values (%s, %s, %s, %s, %s, %s)",
            [(run_id, table, p, e, m, n) for (p, e, m, n) in rows])


def run_load(conn, run_id: str, stage: str = "RAW.ORGANIZER_STAGE", stage_url_prefix: str = "", tables=TABLES) -> dict[str, dict[str, int]]:
    cur = conn.cursor()
    summary: dict[str, dict[str, int]] = {}
    for table, prefix in tables.items():
        files = list_stage_files(cur, stage, prefix, stage_url_prefix)
        manifest = read_manifest(cur, table)
        actions = plan_loads(files, manifest)
        md5 = {f.path: f.md5 for f in files}
        counts = {"new": 0, "restated": 0, "skipped": 0}
        rows: list[tuple[str, str, str, int]] = []
        for mode, force in (("new", False), ("restated", True)):
            paths = [a.path for a in actions if a.mode == mode]
            if paths:
                loaded = copy_files(cur, table, stage, paths, force=force)
                rows += [(p, md5[p], mode, loaded[p]) for p in paths]
                counts[mode] = len(paths)
        counts["skipped"] = sum(1 for a in actions if a.mode == "skipped")
        record_manifest(cur, run_id, table, rows)
        conn.commit()
        summary[table] = counts
        print(f"{table}: {counts}", file=sys.stderr)
    return summary


if __name__ == "__main__":
    from dotenv import load_dotenv
    from pipeline.connect import get_connection

    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=uuid.uuid4().hex[:12])
    ap.add_argument("--database", default=None)
    ap.add_argument("--stage", default="RAW.ORGANIZER_STAGE")
    ap.add_argument("--stage-url-prefix", default=f"s3://{os.environ.get('DATA_BUCKET', '')}/data/")
    a = ap.parse_args()
    with get_connection(a.database) as conn:
        run_load(conn, a.run_id, a.stage, a.stage_url_prefix)
