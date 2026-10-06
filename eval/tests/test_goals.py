from collections import Counter

import pytest
from bankagent.policy.dispute import DisputePolicy

from evalkit.goals import (DEV_MIX, FAMILY, HELDOUT_MIX, GoalCard, GoalGenerationError, make_goals, read_goals,
                           review_sheet, sha256_file, write_goals)
from evalkit.splits import customer_split
from evalkit.universe import Universe
from tests.universe_fixture import AS_OF, build_universe


@pytest.fixture(scope="module")
def universe(tmp_path_factory):
    return Universe(build_universe(tmp_path_factory.mktemp("serving")))


@pytest.fixture(scope="module")
def policy():
    return DisputePolicy.load()


@pytest.fixture(scope="module")
def heldout(universe, policy):
    return make_goals(universe, policy, "heldout", HELDOUT_MIX, seed=7)


def test_mixes_match_the_spec():
    assert sum(HELDOUT_MIX.values()) == 120 and sum(DEV_MIX.values()) == 30
    assert set(HELDOUT_MIX) == set(FAMILY) and set(DEV_MIX) <= set(FAMILY)


def test_heldout_mix_and_languages(heldout):
    assert Counter(c.group for c in heldout) == Counter(HELDOUT_MIX)
    assert Counter(c.language for c in heldout) == {"es": 60, "pt": 60}
    assert len({c.goal_id for c in heldout}) == 120


def test_identities_only_from_their_bucket(universe, policy, heldout):
    assert all(customer_split(c.customer_id) == "test" for c in heldout)
    dev = make_goals(universe, policy, "dev", DEV_MIX, seed=7)
    assert len(dev) == 30 and all(customer_split(c.customer_id) == "dev" for c in dev)


def test_dispute_labels_come_from_the_policy(universe, policy, heldout):
    txns = {t["transaction_id"]: t for ts in universe.window_txns_by_customer().values() for t in ts}
    for c in heldout:
        action = c.expected["action"] or ""
        if action.startswith("dispute:"):
            _, tid, reason = action.split(":", 2)
            assert policy.evaluate(txns[tid], reason, AS_OF, already_disputed=False).outcome == "automated"
        if c.group == "human_policy":
            assert c.expected["outcome"] == "handoff" and c.expected["handoff_reasons"]


def test_targets_and_customers_are_unique(heldout):
    actions = [c.expected["action"] for c in heldout if (c.expected["action"] or "").startswith("dispute:")]
    assert len(actions) == len(set(actions))
    assert len({c.customer_id for c in heldout}) == 120


def test_ambiguous_goals_are_vague_and_hard(heldout):
    amb = [c for c in heldout if c.group == "ambiguous"]
    assert all(c.persona["vagueness"] == "high" and c.expected["outcome"] == "clarify_then_resolve" for c in amb)


def test_faults_and_styles(heldout):
    by = Counter((c.group, c.fault, c.message_style) for c in heldout)
    assert by[("expired", "expire_after_turn_1", "native")] == 4
    assert by[("tool_jev_down", "jev_down", "native")] == 2
    assert by[("ml_english", None, "english")] == 2


def test_persona_view_hides_labels_and_identity(heldout):
    view = heldout[0].persona_view()
    assert "expected" not in view and "customer_id" not in view and "allowed_ids" not in view


def test_same_seed_same_cards(universe, policy, heldout):
    again = make_goals(universe, policy, "heldout", HELDOUT_MIX, seed=7)
    assert [c.to_json() for c in again] == [c.to_json() for c in heldout]
    other = make_goals(universe, policy, "heldout", HELDOUT_MIX, seed=8)
    assert [c.to_json() for c in other] != [c.to_json() for c in heldout]


def test_generator_names_the_group_it_cannot_fill(universe, policy):
    with pytest.raises(GoalGenerationError, match="bad_no_txns"):
        make_goals(universe, policy, "heldout", {"bad_no_txns": 60}, seed=1)


def test_write_read_and_hash(tmp_path, heldout):
    path = tmp_path / "heldout.jsonl"
    digest = write_goals(heldout, path)
    assert digest == sha256_file(path) and len(digest) == 64
    assert [c.to_json() for c in read_goals(path)] == [c.to_json() for c in heldout]
    assert isinstance(read_goals(path)[0], GoalCard)


def test_review_sheet_is_stratified(heldout):
    rows = review_sheet(heldout, n=24)
    assert len(rows) == 24 and len({r["group"] for r in rows}) >= 10
    assert {"goal_id", "group", "language", "hidden_goal", "expected", "reviewer_ok", "correction"} <= set(rows[0])


def _ctx_with_products(products):
    from types import SimpleNamespace
    return SimpleNamespace(products={"CLI-X": products})


def test_account_info_goals_only_use_card_and_account_products():
    from evalkit.goals import _b_account
    loan = {"product_id": "PRD-L", "product_type": "Préstamo Hipotecario", "product_last4": "4436"}
    card = {"product_id": "PRD-C", "product_type": "Tarjeta Crédito", "product_last4": "1111"}
    built = _b_account(_ctx_with_products([loan, card]), {"customer_id": "CLI-X"}, "es", 0)
    assert built["facts"]["last4"] == "1111"
    assert _b_account(_ctx_with_products([loan]), {"customer_id": "CLI-X"}, "es", 0) is None
    assert _b_account(_ctx_with_products([{**loan, "product_type": "Inversión"}]), {"customer_id": "CLI-X"}, "es", 0) is None


def test_unsupported_goals_tell_the_persona_to_decline_an_offered_human(heldout):
    unsupported = [c for c in heldout if c.group == "unsupported"]
    assert unsupported and all("decline" in c.hidden_goal.lower() and c.expected["outcome"] == "abstain"
                               for c in unsupported)


def test_heldout_account_goals_have_no_loans_or_investments(heldout, universe):
    types = {p["product_id"]: p["product_type"] for ps in universe.products_by_customer().values() for p in ps}
    for c in heldout:
        if c.group in ("account_info", "tool_serving_down", "ml_mixed", "ml_english"):
            assert c.revealable_facts["product_type"].startswith(("Tarjeta", "Cuenta"))
