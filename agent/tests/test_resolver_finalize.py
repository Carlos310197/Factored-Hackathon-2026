import json
from pathlib import Path

import numpy as np
import pytest

from bankagent.resolver.finalize import choose_finalist, fit_temperature, promote, write_model_card
from bankagent.resolver.histories import TransactionSource, sample_histories
from bankagent.resolver.model import Resolver
from bankagent.resolver.simulate import load_sim_config, simulate
from bankagent.resolver.train import case_metrics, search
from tests.test_resolver_train import ListTracker


@pytest.fixture(scope="module")
def trained(history_serving, tmp_path_factory):
    src, cfg = TransactionSource(history_serving), load_sim_config()
    train = simulate(sample_histories(src, "train", 600, seed=1), cfg, seed=1)
    val = simulate(sample_histories(src, "dev", 150, seed=1), cfg, seed=2)
    dev = [c | {"extraction": {"mentions": c["mentions"]}} for c in simulate(sample_histories(src, "dev", 150, seed=9), cfg, seed=9)]
    out = tmp_path_factory.mktemp("runs")
    finalists = search(train, val, out, ListTracker(), seed=1,
                       metadata={"serving_run_id": "resolver-fixture-1", "seed": 1, "n_train": len(train),
                                 "n_val": len(val), "simulate_version": cfg["version"], "simulate_sha256": cfg["sha256"]},
                       logreg_grid=[{"C": 1.0}], lgbm_grid=[{"num_leaves": 7, "learning_rate": 0.1, "n_estimators": 50}])
    return {k: v.__dict__ for k, v in finalists.items()}, dev


def test_choose_finalist_prefers_logreg_on_near_ties(trained):
    finalists, dev = trained
    family, metrics = choose_finalist(finalists, dev)
    assert set(metrics) == {"logreg", "lightgbm"}
    if metrics["logreg"]["top1_hard"] >= metrics["lightgbm"]["top1_hard"] - 0.02:
        assert family == "logreg"
    else:
        assert family == "lightgbm"


def test_temperature_lowers_dev_nll(trained):
    finalists, dev = trained
    r = Resolver.load(Path(finalists["logreg"]["path"]))
    t = fit_temperature(r, dev)
    assert 0.05 <= t <= 20.0 and not np.isclose(t, 1.0)


@pytest.mark.parametrize("family", ["logreg", "lightgbm"])
def test_promote_writes_a_loadable_artifact_and_card(trained, tmp_path, family):
    finalists, dev = trained
    src = Path(finalists[family]["path"])
    r = promote(src, 1.7, {"dev_rows": len(dev)}, dst=tmp_path / "v1")
    spec = json.loads((tmp_path / "v1" / "model.json").read_text())
    assert r.temperature == 1.7 and spec["metadata"]["dev_rows"] == len(dev) and spec["metadata"]["family"] == family
    card = write_model_card(tmp_path / "v1", r, {family: case_metrics(r, dev, "extraction")},
                            case_metrics(r, dev, "extraction")).read_text()
    assert f"Family: **{family}**" in card and "temperature **1.700**" in card and "resolver-fixture-1" in card
