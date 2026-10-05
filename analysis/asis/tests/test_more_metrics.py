from asis import artifacts, metrics


def v(d, k):
    return d[k]["value"]


def test_capacity_and_portuguese_coverage(con):
    c = metrics.capacity(con)
    assert c["capacity.pt_agent_share"] == {"value": 0.5, "n": 4}
    assert v(c, "capacity.monthly_load_mean") == 450.0
    assert v(c, "capacity.by_shift.Morning.agents") == 2
    assert c["capacity.by_shift.Morning.contacts_per_agent"] == {"value": 2.5, "n": 5}
    assert c["capacity.by_shift.Afternoon.contacts_per_agent"] == {"value": 0.0, "n": 0}
    assert c["capacity.by_shift.Night.contacts_per_agent"] == {"value": 1.0, "n": 1}


def test_disputes_cover_only_the_two_subcategories(con):
    d = metrics.disputes(con)
    assert d["disputes.count"] == {"value": 2, "n": 2}
    assert d["disputes.first_response_h_p50"] == {"value": 37.0, "n": 2}
    assert v(d, "disputes.resolution_days_p50") == 15.5
    assert v(d, "disputes.sla_breach_rate") == 0.5
    assert v(d, "disputes.backlog_share") == 1.0
    assert v(d, "disputes.by_channel.Call Center") == 0.5
    assert d["complaints.total"] == {"value": 3, "n": 3}


def test_digital_and_transcripts(con):
    assert metrics.digital(con)["digital.monthly.Login"] == {"value": round(2 / 12, 6), "n": 2}
    t = metrics.transcripts(con)
    assert t["transcripts.distinct_customer_text"] == {"value": 2, "n": 4}
    assert v(t, "transcripts.consulta_general_share") == 0.75


def test_fairness_reference_uses_the_in_scope_slice(con):
    f = metrics.fairness(con)
    assert f["fairness.by_country.México.fcr"] == {"value": 1.0, "n": 2}
    assert f["fairness.by_country.Argentina.fcr"] == {"value": 0.0, "n": 1}
    assert v(f, "fairness.by_segment.Retail.fcr") == round(2 / 3, 6)
    assert f["fairness.by_accent.unknown.fcr"] == {"value": 0.0, "n": 1}
    assert v(f, "fairness.by_country.México.handle_time_s_p50") == 150.0
    assert f["fairness.by_country.México.csat_mean"] == {"value": 3.0, "n": 2}


def test_collect_merges_every_group(con):
    keys = metrics.collect(con)
    for prefix in ("demand.", "quality.", "satisfaction.", "capacity.", "disputes.", "digital.", "transcripts.",
                   "fairness.", "complaints."):
        assert any(k.startswith(prefix) for k in keys), prefix


def test_artifact_detectors_on_the_fixture(con):
    a = {x["name"]: x for x in [
        artifacts.escalation_flat(con, min_n=1), artifacts.sla_flat(con, min_n=1), artifacts.wait_constant(con),
        artifacts.csat_by_resolution(con, min_n=1), artifacts.transactional_sentiment_constant(con),
        artifacts.no_pt_customers(con), artifacts.transcripts_templated(con)]}
    assert a["escalation_flat"]["holds"] is False
    assert a["sla_flat"]["holds"] is False
    assert a["wait_constant"]["holds"] is True
    assert a["csat_by_resolution"]["holds"] is False and "insufficient" in a["csat_by_resolution"]["evidence"]
    assert a["transactional_sentiment_constant"]["holds"] is True
    assert a["no_pt_customers"]["holds"] is True
    assert a["transcripts_templated"]["holds"] is False
    assert all(x["query"] and x["evidence"] for x in a.values())


def test_detect_all_names(con):
    assert [x["name"] for x in artifacts.detect_all(con)] == [
        "escalation_flat", "sla_flat", "wait_constant", "csat_by_resolution", "transactional_sentiment_constant",
        "no_pt_customers", "transcripts_templated"]
