"""Offline only: never imported by the agent at runtime."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from bankagent.resolver.features import FEATURES, case_features
from bankagent.resolver.model import Resolver

VERSION = "resolver.v1"
LOGREG_GRID = [{"C": c} for c in (0.01, 0.1, 1.0, 10.0, 100.0)]
LGBM_GRID = [{"num_leaves": nl, "learning_rate": lr, "n_estimators": ne}
             for nl in (7, 15, 31) for lr in (0.05, 0.1) for ne in (200, 500)]
ECE_BINS = 10


@dataclass(frozen=True)
class Finalist:
    family: str
    params: dict
    path: str
    val_metrics: dict


def build_matrix(cases: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    for c in cases:
        xs.append(case_features(c["mentions"], c["candidates"]))
        ys.append(np.array([t["transaction_id"] == c["target_id"] for t in c["candidates"]], dtype=float))
    return np.vstack(xs), np.concatenate(ys)


def _selfcheck(resolver: Resolver, X: np.ndarray) -> dict:
    rows = X[:20]
    return {"X": rows.tolist(), "logits": resolver.raw(rows)[0].tolist()}


def fit_logreg(X: np.ndarray, y: np.ndarray, C: float, seed: int, out_dir: Path, metadata: dict) -> Resolver:
    from sklearn.linear_model import LogisticRegression

    mean, scale = X.mean(axis=0), X.std(axis=0)
    scale[scale == 0] = 1.0
    lr = LogisticRegression(C=C, max_iter=2000, random_state=seed).fit((X - mean) / scale, y)
    spec = {"version": VERSION, "kind": "logreg", "features": list(FEATURES), "mean": mean.tolist(),
            "scale": scale.tolist(), "coef": lr.coef_[0].tolist(), "intercept": float(lr.intercept_[0]),
            "temperature": 1.0, "metadata": metadata | {"family": "logreg", "params": {"C": C}}}
    return _save(spec, out_dir, X)


def fit_lightgbm(X: np.ndarray, y: np.ndarray, params: dict, seed: int, out_dir: Path, metadata: dict) -> Resolver:
    import lightgbm as lgb

    out_dir.mkdir(parents=True, exist_ok=True)
    common = params | {"random_state": seed, "verbose": -1, "deterministic": True, "force_row_wise": True}
    lgb.LGBMClassifier(objective="binary", **common).fit(X, y).booster_.save_model(out_dir / "model.txt")
    spec = {"version": VERSION, "kind": "lightgbm", "features": list(FEATURES), "model_file": "model.txt",
            "temperature": 1.0, "metadata": metadata | {"family": "lightgbm", "params": params}}
    return _save(spec, out_dir, X)


def _save(spec: dict, out_dir: Path, X: np.ndarray) -> Resolver:
    out_dir.mkdir(parents=True, exist_ok=True)
    resolver = Resolver(spec, out_dir)
    spec["selfcheck"] = _selfcheck(resolver, X)
    (out_dir / "model.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    return Resolver.load(out_dir)


def case_metrics(resolver: Resolver, cases: list[dict], mentions_key: str = "mentions") -> dict:
    from sklearn.metrics import roc_auc_score

    hits, conf, present, fit = {"all": [], "hard": [], "easy": []}, [], [], []
    for c in cases:
        m = c[mentions_key]["mentions"] if mentions_key == "extraction" else c[mentions_key]
        s = resolver.score(c["candidates"], m)
        present.append(c["target_id"] is not None)
        fit.append(s.best_raw_fit)
        if c["target_id"] is None:
            continue
        hit = s.ranked[0] == c["target_id"]
        hits["all"].append(hit)
        hits[c["slice"]].append(hit)
        conf.append((s.probs[s.ranked[0]], hit))
    mean = lambda v: float(np.mean(v)) if v else None  # noqa: E731
    auc = float(roc_auc_score(present, fit)) if len(set(present)) == 2 else None
    return {"n": len(cases), "n_hard": len(hits["hard"]), "top1": mean(hits["all"]), "top1_hard": mean(hits["hard"]),
            "top1_easy": mean(hits["easy"]), "nil_auc": auc, "ece": expected_calibration_error(conf)}


def expected_calibration_error(conf: list[tuple[float, bool]], bins: int = ECE_BINS) -> float | None:
    if not conf:
        return None
    p = np.array([c for c, _ in conf])
    ok = np.array([h for _, h in conf], dtype=float)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(p[idx == b].mean() - ok[idx == b].mean()) * (idx == b).sum()
                     for b in range(bins) if (idx == b).any()) / len(p))


def _key(m: dict) -> tuple:
    return (m["top1_hard"] or 0.0, m["top1"] or 0.0)


def search(train_cases: list[dict], val_cases: list[dict], out_dir: Path, tracker, seed: int, metadata: dict,
           logreg_grid: list[dict] = LOGREG_GRID, lgbm_grid: list[dict] = LGBM_GRID) -> dict[str, Finalist]:
    X, y = build_matrix(train_cases)
    best: dict[str, Finalist] = {}
    runs = [("logreg", p) for p in logreg_grid] + [("lightgbm", p) for p in lgbm_grid]
    for i, (family, params) in enumerate(runs):
        path = out_dir / f"{family}-{i:02d}"
        if family == "logreg":
            model = fit_logreg(X, y, params["C"], seed, path, metadata)
        else:
            model = fit_lightgbm(X, y, params, seed, path, metadata)
        m = case_metrics(model, val_cases)
        tracker.log(f"{family}-{i:02d}", metadata | params | {"family": family}, m, path)
        if family not in best or _key(m) > _key(best[family].val_metrics):
            best[family] = Finalist(family, params, str(path), m)
    (out_dir / "finalists.json").write_text(json.dumps({k: v.__dict__ for k, v in best.items()}, indent=1))
    return best
