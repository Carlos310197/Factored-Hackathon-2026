import pytest

from asis import metrics
from asis.load import connect


def v(d, k):
    return d[k]["value"]


def test_quality_uses_the_window_and_matches_hand_counts(con):
    q = metrics.quality(con)
    assert q["quality.Transaccional.fcr"] == {"value": 0.75, "n": 4}  # INT-FIX0 (2024) is outside the window
    assert v(q, "quality.Transaccional.escalation_rate") == 0.25
    assert v(q, "quality.Transaccional.followup_rate") == 0.25
    assert q["quality.Transaccional.handle_time_s_p50"] == {"value": 210.0, "n": 4}
    assert v(q, "quality.Transaccional.handle_time_s_p90") == 282.0
    assert v(q, "quality.Transaccional.wait_time_s_p50") == 120.0
    assert q["quality.Queja.fcr"] == {"value": 0.5, "n": 2}


def test_spanish_sentiment_labels_are_normalized(con):
    assert v(metrics.quality(con), "quality.Queja.negative_sentiment_share") == 1.0


def test_demand(con):
    d = metrics.demand(con)
    assert v(d, "demand.by_hour.09") == 2 and v(d, "demand.by_hour.23") == 1
    assert v(d, "demand.by_channel.Phone") == round(5 / 6, 6)
    assert v(d, "demand.trend.2024-01") == 1 and v(d, "demand.trend.2026-06") == 6
    assert d["demand.in_scope_per_month"] == {"value": 0.5, "n": 6}
    assert d["demand.total"] == {"value": 6, "n": 6}


def test_satisfaction_through_the_survey_link(con):
    s = metrics.satisfaction(con)
    assert s["satisfaction.Transaccional.CSAT.mean"] == {"value": round(8 / 3, 6), "n": 3}
    assert s["satisfaction.csat_resolved.mean"] == {"value": 3.0, "n": 2}
    assert s["satisfaction.csat_unresolved.mean"] == {"value": 2.0, "n": 1}
    assert s["satisfaction.Queja.nps_detractor_share"] == {"value": 1.0, "n": 1}
    assert s["satisfaction.link_rate"] == {"value": 1.0, "n": 4}


def test_backup_prefix_is_refused(tmp_path):
    with pytest.raises(ValueError):
        connect(tmp_path / "data_backup_20260831")


def test_customer_pii_columns_are_not_exposed(con):
    cols = {r[0] for r in con.sql("describe customers").fetchall()}
    assert cols == {"customer_id", "country", "segment", "detected_accent"}
