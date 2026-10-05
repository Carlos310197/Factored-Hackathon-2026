import json

from evalkit.agent_runtime import table_prefix
from evalkit.goals import write_goals
from evalkit.run import load_done, main, manifest, pending
from tests.helpers import make_card


def test_table_prefix_is_unique_per_rep():
    assert len({table_prefix("20261003-heldout", r) for r in (1, 2, 3)}) == 3
    assert table_prefix("20261003-heldout", 2) == "eval-20261003-heldout-r2"


def test_pending_skips_finished_pairs():
    cards = [make_card(goal_id="H001-a"), make_card(goal_id="H002-b")]
    todo = pending(cards, 2, {("H001-a", 1)})
    assert [(c.goal_id, r) for c, r in todo] == [("H002-b", 1), ("H001-a", 2), ("H002-b", 2)]


def test_load_done_reads_jsonl(tmp_path):
    p = tmp_path / "conversations.jsonl"
    p.write_text(json.dumps({"goal_id": "H001-a", "rep": 1}) + "\n" + json.dumps({"goal_id": "H001-a", "rep": 2}) + "\n")
    assert load_done(p) == {("H001-a", 1), ("H001-a", 2)}
    assert load_done(tmp_path / "missing.jsonl") == set()


def test_manifest_records_the_goal_hash(tmp_path):
    goals = tmp_path / "g.jsonl"
    digest = write_goals([make_card()], goals)
    cfg = {"persona": {"model": "m"}, "judge": {"model": "j"}}
    m = manifest("r1", goals, 3, cfg)
    assert m["goals_sha256"] == digest and m["reps"] == 3 and m["persona_model"] == "m"
    assert "extract" in m["agent_models"] and m["git_sha"]


def test_main_refuses_without_live(tmp_path, capsys):
    goals = tmp_path / "g.jsonl"
    write_goals([make_card()], goals)
    assert main(["--goals", str(goals), "--run-id", "x"]) == 2
    assert "--live" in capsys.readouterr().out
