import json

from bankagent.llm.config import load_models
from bankagent.resolver.devset import build_dev_set, details_en
from bankagent.resolver.histories import TransactionSource, sample_histories
from bankagent.resolver.simulate import load_sim_config
from tests.resolver_llm import ScriptedLLM

M = load_models(env={})


def test_dev_rows_are_balanced_labeled_and_private(history_serving):
    hs = sample_histories(TransactionSource(history_serving), "dev", 40, seed=2)
    llm = ScriptedLLM(mentions={"amount": 12.5})
    rows, skipped = build_dev_set(hs, load_sim_config(), seed=2, n=12, client=llm, models=M)
    assert len(rows) == 12 and skipped == 0
    assert [r["lang"] for r in rows] == ["es", "pt"] * 6
    for r in rows:
        ids = [t["transaction_id"] for t in r["candidates"]]
        assert (r["target_id"] in ids) if r["slice"] != "nil" else (r["target_id"] is None and r["target"]["transaction_id"] not in ids)
        assert r["extraction"]["mentions"]["amount"] == 12.5 and r["style"]["extract_error"] is False
        assert r["versions"]["writer"] == [M["dev_writer"].model, "devwriter.v1"]
        assert r["versions"]["extract"][1] == "extract.v2" and r["country"] == "México"
    dumped = json.dumps(rows)
    assert "CLI-" not in dumped and "PRD-" not in dumped


def test_writer_sees_only_the_details(history_serving):
    hs = sample_histories(TransactionSource(history_serving), "dev", 10, seed=4)
    llm = ScriptedLLM()
    rows, _ = build_dev_set(hs, load_sim_config(), seed=4, n=3, client=llm, models=M)
    writer_prompts = [c["messages"][1]["content"] for c in llm.calls if "response_format" not in c]
    for prompt, row in zip(writer_prompts, rows):
        others = [t for t in row["candidates"] if t["transaction_id"] != row["target_id"]]
        assert all(t["transaction_id"] not in prompt for t in row["candidates"])
        assert all(f"{t['amount']:g}" not in prompt for t in others if t["amount"] != row["target"]["amount"])


def test_llm_failures_are_skipped_not_fatal(history_serving):
    hs = sample_histories(TransactionSource(history_serving), "dev", 30, seed=5)
    rows, skipped = build_dev_set(hs, load_sim_config(), seed=5, n=5, client=ScriptedLLM(fail_every=3), models=M)
    assert len(rows) == 5 and skipped >= 1


def test_details_render_the_style():
    case = {"anchor": "2026-06-17", "style": {"amount": "rounded", "date": "relative", "date_label": "last week",
                                              "no_detail": False},
            "mentions": {"merchant": "tienda don jose", "amount": 340.0, "currency": "USD", "date_from": "2026-06-08",
                         "date_to": "2026-06-14", "type_hint": None, "channel_hint": "pos", "city": None}}
    d = details_en(case)
    assert d[0] == 'the merchant name as the customer writes it: "tienda don jose"'
    assert d[1] == "the amount: about 340 USD" and d[2].startswith("when: last week")
    assert d[3] == "it happened with the card in a shop"
    assert details_en(case | {"style": {"no_detail": True}})[0].startswith("no specific details")


def test_amounts_are_written_in_plain_digits():
    case = {"anchor": "2026-06-17", "style": {"amount": "exact", "date": "absent", "no_detail": False},
            "mentions": {"merchant": None, "amount": 33984700.0, "currency": "COP", "date_from": None, "date_to": None,
                         "type_hint": None, "channel_hint": None, "city": None}}
    assert details_en(case) == ["the amount: exactly 33984700 COP"]
    assert details_en(case | {"mentions": case["mentions"] | {"amount": 56.56}}) == ["the amount: exactly 56.56 COP"]


def test_writer_accepts_plain_text_even_with_stray_braces():
    from bankagent.resolver.devset import write_message

    class Raw:
        def __init__(self, text):
            self.chat = type("C", (), {"completions": self})()
            self.text = text

        def create(self, **kw):
            from types import SimpleNamespace as N
            assert "response_format" not in kw
            return N(choices=[N(message=N(content=self.text), finish_reason="stop")], usage=N(prompt_tokens=1, completion_tokens=1))

    case = {"anchor": "2026-06-17", "style": {"no_detail": True}, "mentions": {}}
    got = write_message(Raw('  "Hola, no reconozco un cargo."  \n'), M["dev_writer"], case, "es", "dispute")
    assert got.data["message"] == "Hola, no reconozco un cargo." and got.prompt_version == "devwriter.v1"
