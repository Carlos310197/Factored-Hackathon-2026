import json

import pytest

from bankagent.resolver.model import Resolver, ResolverUnavailable
from tests.resolver_data import mentions, txn, write_logreg_artifact

CANDS = [txn(1, day="2026-06-12", merchant=None, ttype="Withdrawal", amount=120.0),
         txn(2, day="2026-06-10", amount=343.03), txn(3, day="2026-05-20", merchant="Super Ahorro", amount=340.0)]
M = mentions(merchant="tienda don jose", amount=340, date_from="2026-06-08", date_to="2026-06-14")


def test_scores_sum_to_one_and_rank_the_described_transaction_first(tmp_path):
    write_logreg_artifact(tmp_path)
    s = Resolver.load(tmp_path).score(CANDS, M)
    assert abs(sum(s.probs.values()) + s.p_none - 1.0) < 1e-9
    assert s.ranked[0] == txn(2)["transaction_id"] and s.probs[s.ranked[0]] > 0.8
    assert 0.0 < s.best_raw_fit < 1.0 and s.version == "resolver.test"
    top = dict(s.contributions[txn(2)["transaction_id"]])
    assert len(top) == 3 and "merchant_sim" in top


def test_temperature_flattens_probabilities(tmp_path):
    write_logreg_artifact(tmp_path / "t1")
    write_logreg_artifact(tmp_path / "t3", temperature=3.0)
    p1 = Resolver.load(tmp_path / "t1").score(CANDS, M)
    p3 = Resolver.load(tmp_path / "t3").score(CANDS, M)
    assert p3.probs[p3.ranked[0]] < p1.probs[p1.ranked[0]] and p3.ranked == p1.ranked
    assert p3.best_raw_fit == p1.best_raw_fit


def test_no_mentions_gives_flat_ranking_and_low_fit(tmp_path):
    write_logreg_artifact(tmp_path)
    s = Resolver.load(tmp_path).score(CANDS, mentions())
    assert max(s.probs.values()) - min(s.probs.values()) < 1e-9 and s.best_raw_fit < 0.5
    empty = Resolver.load(tmp_path).score([], M)
    assert empty.probs == {} and empty.p_none == 1.0


def test_a_lone_candidate_that_does_not_fit_gets_a_low_match(tmp_path):
    write_logreg_artifact(tmp_path)
    r = Resolver.load(tmp_path)
    lone = [txn(3, day="2026-05-20", merchant="Super Ahorro", amount=12.0)]
    bad = r.score(lone, M)
    assert bad.probs[lone[0]["transaction_id"]] < 0.2 and bad.p_none > 0.8
    good = r.score([txn(2, day="2026-06-10", amount=343.03)], M)
    assert good.probs[txn(2)["transaction_id"]] > 0.8


def test_missing_corrupt_or_tampered_artifact_is_unavailable(tmp_path):
    with pytest.raises(ResolverUnavailable):
        Resolver.load(tmp_path / "nothing")
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "model.json").write_text("{not json")
    with pytest.raises(ResolverUnavailable):
        Resolver.load(tmp_path / "bad")
    write_logreg_artifact(tmp_path / "tampered")
    spec = json.loads((tmp_path / "tampered" / "model.json").read_text())
    spec["coef"][1] += 0.5
    (tmp_path / "tampered" / "model.json").write_text(json.dumps(spec))
    with pytest.raises(ResolverUnavailable, match="self-check"):
        Resolver.load(tmp_path / "tampered")
    write_logreg_artifact(tmp_path / "wrongfeat")
    spec = json.loads((tmp_path / "wrongfeat" / "model.json").read_text())
    spec["features"] = spec["features"][::-1]
    (tmp_path / "wrongfeat" / "model.json").write_text(json.dumps(spec))
    with pytest.raises(ResolverUnavailable, match="features"):
        Resolver.load(tmp_path / "wrongfeat")
