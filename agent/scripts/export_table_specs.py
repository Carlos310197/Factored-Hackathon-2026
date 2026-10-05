"""Write infra/terraform/data/tables.json from TABLE_SPECS (the single source for the table shapes).
Run: cd agent && uv run python scripts/export_table_specs.py"""
import json
from pathlib import Path

from bankagent.store.tables import STREAM_SPEC, STREAM_TABLES, TABLE_SPECS

OUT = Path(__file__).resolve().parents[2] / "infra/terraform/data/tables.json"


def _key(keys, kind):
    return next((a for a, _, k in keys if k == kind), None)


def build() -> dict:
    out = {}
    for name, spec in TABLE_SPECS.items():
        attrs = {a: t for a, t, _ in spec["keys"]}
        for _, keys in spec["gsis"]:
            attrs.update({a: t for a, t, _ in keys})
        out[name] = {
            "hash_key": _key(spec["keys"], "HASH"),
            "range_key": _key(spec["keys"], "RANGE"),
            "attributes": [{"name": a, "type": t} for a, t in attrs.items()],
            "gsis": [{"name": n, "hash_key": _key(keys, "HASH"), "range_key": _key(keys, "RANGE")}
                     for n, keys in spec["gsis"]],
            "ttl": spec["ttl"],
            "stream_view_type": STREAM_SPEC["StreamViewType"] if name in STREAM_TABLES else None,
        }
    return out


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2) + "\n")
