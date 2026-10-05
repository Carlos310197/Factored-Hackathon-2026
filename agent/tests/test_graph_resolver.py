from bankagent.resolver.model import Resolver
from tests.fakes import FakeLLM
from tests.harness import CTX_ES, make_harness
from tests.resolver_data import write_logreg_artifact

NETFLIX = {"merchant": "Netflix", "amount": 15.99, "date_from": "2026-06-10", "date_to": "2026-06-10"}
STATUS = {"intent": "transaction_status", "target": "Netflix"}


class BrokenResolver:
    version = "resolver.broken"

    def score(self, candidates, mentions):
        raise RuntimeError("boom")


def records(h, kind):
    return [r for r in h.store.log.list(CTX_ES.session_id) if r["kind"] == kind]


def test_scores_reach_jev_with_understand_v2(ddb_store, serving_root, tmp_path):
    write_logreg_artifact(tmp_path)
    h = make_harness(ddb_store, serving_root, [STATUS], llm=FakeLLM(mentions=NETFLIX), resolver=Resolver.load(tmp_path))
    r = h.turn("¿Pasó mi cargo de Netflix del 10 de junio?")
    assert r["reply_text"]
    _, state, questions = h.jev.calls[0]
    assert all(" · match " in d for a, d in questions["target_transaction"]["criteria"].items() if a.startswith("c"))
    assert all("match" in c for c in state["candidate_transactions"])
    model = records(h, "model")
    assert len(model) == 1 and model[0]["versions"] == {"resolver": "resolver.test"}
    payload = model[0]["payload"]
    assert abs(sum(payload["probs"].values()) + payload["p_none"] - 1.0) < 1e-6
    assert records(h, "jev")[0]["versions"]["question_set"] == "understand.v2"
    assert h.state()["decisions"][0]["question_set"] == "understand.v2"


def test_resolver_failure_falls_back_to_v1(ddb_store, serving_root):
    h = make_harness(ddb_store, serving_root, [STATUS], llm=FakeLLM(mentions=NETFLIX), resolver=BrokenResolver())
    r = h.turn("¿Pasó mi cargo de Netflix del 10 de junio?")
    assert r["reply_text"]
    errors = [e for e in records(h, "error") if e["payload"].get("role") == "resolver"]
    assert len(errors) == 1 and errors[0]["payload"]["error"] == "boom"
    assert not records(h, "model")
    assert records(h, "jev")[0]["versions"]["question_set"] == "understand.v1"
    assert all(" · match " not in d for d in h.jev.calls[0][2]["target_transaction"]["criteria"].values())


def test_no_extraction_means_no_scores(ddb_store, serving_root, tmp_path):
    write_logreg_artifact(tmp_path)
    h = make_harness(ddb_store, serving_root, [STATUS], llm=FakeLLM(fail=("extract",)), resolver=Resolver.load(tmp_path))
    h.turn("¿Pasó mi cargo de Netflix?")
    assert not records(h, "model") and records(h, "jev")[0]["versions"]["question_set"] == "understand.v1"
