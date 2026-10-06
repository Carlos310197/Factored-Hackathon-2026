import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from bankagent.resolver.features import FEATURES, case_features

ARTIFACT_DIR = Path(__file__).with_name("artifacts") / "v1"
SELFCHECK_TOL = 1e-6


class ResolverUnavailable(Exception):
    """The artifact is missing, corrupt or fails its self-check; the agent continues without scores."""


@dataclass(frozen=True)
class Scores:
    probs: dict[str, float]  # per candidate; together with p_none they sum to 1
    p_none: float  # probability that the described transaction is not among the candidates
    ranked: list[str]
    best_raw_fit: float  # sigmoid of the top candidate's uncalibrated logit (absolute fit)
    contributions: dict[str, list[tuple[str, float]]]
    version: str


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def with_none(logits: np.ndarray, temperature: float) -> np.ndarray:
    """Softmax over the candidates' logits / T plus a 'none of these' logit fixed at 0 (last element)."""
    z = np.append(logits / temperature, 0.0)
    e = np.exp(z - z.max())
    return e / e.sum()


class Resolver:
    def __init__(self, spec: dict, root: Path):
        if tuple(spec["features"]) != FEATURES:
            raise ResolverUnavailable("artifact features do not match features.py")
        self.spec, self.kind, self.temperature = spec, spec["kind"], float(spec.get("temperature", 1.0))
        self.version = spec["version"]
        if self.kind == "logreg":
            self.mean, self.scale = np.array(spec["mean"]), np.array(spec["scale"])
            self.coef, self.intercept = np.array(spec["coef"]), float(spec["intercept"])
        elif self.kind == "lightgbm":
            import lightgbm as lgb
            self.booster = lgb.Booster(model_file=str(root / spec["model_file"]))
        else:
            raise ResolverUnavailable(f"unknown artifact kind {self.kind!r}")

    @classmethod
    def load(cls, path: Path = ARTIFACT_DIR) -> "Resolver":
        try:
            spec = json.loads((Path(path) / "model.json").read_text(encoding="utf-8"))
            r = cls(spec, Path(path))
            check = spec.get("selfcheck")
            if check:
                got = r.raw(np.array(check["X"]))[0]
                if not np.allclose(got, np.array(check["logits"]), atol=SELFCHECK_TOL):
                    raise ResolverUnavailable("artifact self-check failed")
            return r
        except ResolverUnavailable:
            raise
        except Exception as e:
            raise ResolverUnavailable(f"cannot load resolver artifact: {e}") from e

    def raw(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.kind == "logreg":
            z = (X - self.mean) / self.scale
            contrib = z * self.coef
            return contrib.sum(axis=1) + self.intercept, contrib
        return self.booster.predict(X, raw_score=True), self.booster.predict(X, pred_contrib=True)[:, :-1]

    def score(self, candidates: list[dict], mentions: dict | None) -> Scores:
        if not candidates:
            return Scores({}, 1.0, [], 0.0, {}, self.version)
        logits, contrib = self.raw(case_features(mentions, candidates))
        p = with_none(logits, self.temperature)
        ids = [t["transaction_id"] for t in candidates]
        order = list(np.argsort(-logits, kind="stable"))
        contributions = {}
        for i, tid in enumerate(ids):
            top = np.argsort(-np.abs(contrib[i]), kind="stable")[:3]
            contributions[tid] = [(FEATURES[j], round(float(contrib[i, j]), 4)) for j in top]
        return Scores({tid: float(pi) for tid, pi in zip(ids, p[:-1])}, float(p[-1]), [ids[i] for i in order],
                      float(_sigmoid(logits[order[0]])), contributions, self.version)
