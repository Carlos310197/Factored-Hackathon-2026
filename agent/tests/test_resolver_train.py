import pytest

from bankagent.resolver.features import FEATURES
from bankagent.resolver.histories import TransactionSource, sample_histories
from bankagent.resolver.model import Resolver
from bankagent.resolver.simulate import load_sim_config, simulate
from bankagent.resolver.train import build_matrix, case_metrics, expected_calibration_error, search


class ListTracker:
    def __init__(self):
        self.runs = []

    def log(self, run_name, params, metrics, artifact_dir):
        self.runs.append((run_name, params, metrics, artifact_dir))


@pytest.fixture(scope="module")
def cases(history_serving):
    src, cfg = TransactionSource(history_serving), load_sim_config()
    train = simulate(sample_histories(src, "train", 600, seed=1), cfg, seed=1)
    val = simulate(sample_histories(src, "dev", 200, seed=1), cfg, seed=2)
    return train, val


def test_build_matrix_shapes(cases):
    train, _ = cases
    X, y = build_matrix(train)
    assert X.shape == (sum(len(c["candidates"]) for c in train), len(FEATURES)) and len(y) == X.shape[0]
    assert y.sum() == sum(c["target_id"] is not None for c in train)


def test_search_logs_every_run_and_keeps_one_finalist_per_family(cases, tmp_path):
    train, val = cases
    tracker = ListTracker()
    finalists = search(train, val, tmp_path, tracker, seed=1, metadata={"serving_run_id": "resolver-fixture-1"},
                       logreg_grid=[{"C": 0.1}, {"C": 1.0}],
                       lgbm_grid=[{"num_leaves": 7, "learning_rate": 0.1, "n_estimators": 50}])
    assert [r[0] for r in tracker.runs] == ["logreg-00", "logreg-01", "lightgbm-02"]
    assert set(finalists) == {"logreg", "lightgbm"} and (tmp_path / "finalists.json").exists()
    for f in finalists.values():
        reloaded = Resolver.load(f.path)
        assert case_metrics(reloaded, val) == f.val_metrics
        assert f.val_metrics["top1"] > 0.6 and f.val_metrics["nil_auc"] > 0.6
    lr = Resolver.load(finalists["logreg"].path)
    coef = dict(zip(FEATURES, lr.coef))
    assert coef["amount_log_err"] < 0 and coef["days_outside"] < 0 and coef["merchant_sim"] > 0


def test_expected_calibration_error():
    assert expected_calibration_error([(0.9, True)] * 9 + [(0.9, False)]) < 1e-9
    assert abs(expected_calibration_error([(0.9, False)] * 10) - 0.9) < 1e-9
    assert expected_calibration_error([]) is None


def test_mlflow_tracker_logs_a_run(tmp_path):
    import mlflow

    from bankagent.resolver.tracking import MlflowTracker

    art = tmp_path / "art"
    art.mkdir()
    (art / "model.json").write_text("{}")
    MlflowTracker(tmp_path / "mlruns").log("logreg-00", {"C": 1.0, "family": "logreg", "skip": None},
                                           {"top1": 0.9, "nil_auc": None}, art)
    runs = mlflow.search_runs(experiment_names=["transaction-resolver"])
    assert list(runs["tags.mlflow.runName"]) == ["logreg-00"] and runs["metrics.top1"][0] == 0.9
    assert list((tmp_path / "mlruns" / "artifacts").rglob("model.json"))
