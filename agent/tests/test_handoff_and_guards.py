from datetime import datetime, timezone

import boto3
import pydantic
import pytest
from moto import mock_aws

from bankagent.context import SCOPE_READ, SessionContext
from bankagent.guards import unknown_ids
from bankagent.handoff.packet import build_packet, priority_for
from bankagent.policy.dispute import DisputePolicy
from bankagent.store.repos import Store
from bankagent.store.tables import create_tables
from bankagent.tools.write import WriteTools
from tests.fixtures.serving_fixture import C1, t

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
RECEIPT = {"receipt_id": "RCP-1", "source": "fct_transaction", "as_of": "2026-06-17",
           "data": {"transaction_id": t(108), "amount": 60.0}}


def packet(**over):
    kw = dict(session_id="S-1", customer_id=C1, language="es", data_as_of="2026-06-17",
              reason_codes=["reports_unauthorized_use"], customer_request={"original": "No reconozco", "en": "I don't recognize"},
              receipts=[RECEIPT], actions=[{"action": "dispute_drafted", "result": "pending_review", "receipt_id": "RCP-2"}],
              decisions=[{"question": "reports_unauthorized_use", "value": 0.91, "question_set": "understand.v1",
                          "thresholds": "thresholds.v1"}],
              policy_checks=[{"name": "within_window", "passed": True, "detail": "6 days"}],
              open_questions=["Is the card still in the customer's possession?"], now=NOW)
    return build_packet(**{**kw, **over})


def test_packet_shape_and_priority():
    p = packet()
    assert p.schema_version == "handoff.v1" and p.handoff_id.startswith("HND-") and p.status == "open"
    assert p.priority == "critical" and p.verified_facts[0].receipt_id == "RCP-1"
    assert p.policy_checks[0].rule == "within_window" and p.transcript_ref == "session:S-1"


@pytest.mark.parametrize("codes,expected", [(["fraud_flag"], "critical"), (["legal_or_regulator_threat"], "high"),
                                            (["injection_repeated"], "high"), (["amount_over_limit"], "medium"),
                                            ([], "medium")])
def test_priority_for(codes, expected):
    assert priority_for(codes) == expected


def test_packet_rejects_more_than_three_open_questions():
    with pytest.raises(pydantic.ValidationError):
        packet(open_questions=["a", "b", "c", "d"])


def test_create_handoff_writes_and_reads_back():
    with mock_aws():
        create_tables(boto3.client("dynamodb", region_name="us-east-2"), "t")
        store = Store.connect("t", "us-east-2")
        p = packet().model_dump()
        r = WriteTools(store, DisputePolicy.load()).create_handoff(
            SessionContext(C1, "S-1", frozenset({SCOPE_READ}), "es", 0), p, "2026-06-17")
        assert r.source == "handoffs" and r.data["handoff_id"] == p["handoff_id"]
        assert store.handoffs.get(p["handoff_id"])["priority"] == "critical"
        assert store.handoffs.list_by_status("open")[0]["handoff_id"] == p["handoff_id"]


def test_unknown_ids_flags_foreign_and_customer_ids():
    text = f"Tu disputa DSP-1759140000000A1B2C3D4 sobre {t(101)}; también {t(200)} y CLI-FIXC00000001."
    assert unknown_ids(text, {t(101), "DSP-1759140000000A1B2C3D4"}) == {t(200), "CLI-FIXC00000001"}


def test_unknown_ids_ignores_plain_text():
    assert unknown_ids("Tu tarjeta ****4242 tiene saldo de 1,250.40 USD", set()) == set()
