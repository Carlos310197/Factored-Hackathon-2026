import json

from scripts.export_table_specs import OUT, build


def test_committed_json_matches_table_specs():
    assert json.loads(OUT.read_text()) == build(), "run: cd agent && uv run python scripts/export_table_specs.py"
