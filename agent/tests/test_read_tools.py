from datetime import date

import pytest

from bankagent.context import SCOPE_READ, PermissionDenied, SessionContext
from bankagent.data.serving import ServingData
from bankagent.tools.read import NotDeclined, NotFound, ReadTools
from tests.fixtures.serving_fixture import C1, C2, P1, RUN_ID, t

CTX1 = SessionContext(C1, "S-1", frozenset({SCOPE_READ}), "es", 0)
CTX2 = SessionContext(C2, "S-2", frozenset({SCOPE_READ}), "pt", 0)
AS = date(2026, 6, 17)


@pytest.fixture
def tools(serving_root):
    return ReadTools(ServingData(str(serving_root)))


def test_accounts_only_own(tools):
    r = tools.get_accounts(CTX1, RUN_ID, AS)
    assert [a["product_id"] for a in r.data] == [P1]
    assert r.receipt()["source"] == "dim_product" and r.receipt_id.startswith("RCP-") and r.as_of == "2026-06-17"


def test_list_transactions_window_and_order(tools):
    ids = [x["transaction_id"] for x in tools.list_transactions(CTX1, RUN_ID, AS).data]
    assert ids == [t(103), t(102), t(105), t(108), t(101), t(100), t(107), t(104)]


def test_foreign_and_missing_transactions_are_indistinguishable(tools):
    with pytest.raises(NotFound) as foreign:
        tools.get_transaction(CTX1, RUN_ID, AS, t(200))
    with pytest.raises(NotFound) as missing:
        tools.get_transaction(CTX1, RUN_ID, AS, "TRX-DOESNOTEXIST000000")
    assert str(foreign.value) == str(missing.value) == "not_found"


def test_explain_decline_uses_seed(tools):
    r = tools.explain_decline(CTX1, RUN_ID, AS, t(102))
    assert r.source == "seed_decline_reason" and r.data["reason_key"] == "insufficient_funds"
    assert "saldo" in r.data["customer_text_es"] and "saldo" in r.data["customer_text_pt"]
    assert r.data["transaction"]["transaction_id"] == t(102)


def test_explain_decline_on_approved_raises(tools):
    with pytest.raises(NotDeclined):
        tools.explain_decline(CTX1, RUN_ID, AS, t(100))


def test_complaints_scoped(tools):
    assert tools.list_complaints(CTX1, RUN_ID, AS).data[0]["status"] == "In Process"
    assert tools.list_complaints(CTX2, RUN_ID, AS).data == []


def test_scope_required(tools):
    no_scope = SessionContext(C1, "S-1", frozenset(), "es", 0)
    with pytest.raises(PermissionDenied):
        tools.get_accounts(no_scope, RUN_ID, AS)
