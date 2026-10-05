import json

from scripts.resolver import main


def dirs(tmp_path):
    return ["--data-dir", str(tmp_path / "data"), "--reports-dir", str(tmp_path / "reports"),
            "--runs-dir", str(tmp_path / "runs"), "--artifact", str(tmp_path / "artifact"),
            "--thresholds-out", str(tmp_path / "thresholds.v2.yaml")]


def test_live_commands_refuse_without_live(tmp_path, capsys):
    assert main(dirs(tmp_path) + ["jev", "--set", "dev", "--system", "P"]) == 2
    assert main(dirs(tmp_path) + ["dev-set"]) == 2
    assert main(dirs(tmp_path) + ["ingest-test", "--completed", "x.csv"]) == 2
    assert "--live" in capsys.readouterr().err


def test_test_sheet_command(tmp_path, history_serving):
    assert main(dirs(tmp_path) + ["test-sheet", "--serving", str(history_serving)]) == 0
    cases = json.loads((tmp_path / "data" / "test_sheet_v1.json").read_text())
    assert len(cases) == 150 and (tmp_path / "data" / "test_sheet_v1.csv").exists()
