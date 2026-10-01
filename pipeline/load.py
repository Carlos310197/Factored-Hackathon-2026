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
