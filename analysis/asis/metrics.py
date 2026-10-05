"""As-is metrics (evaluation spec §3.2). Every metric is {"value": float|int|None, "n": int} under a flat dotted key."""
from asis.load import MONTHS_IN_WINDOW

IN_SCOPE_REASON = "Transaccional"
DISPUTE_SUBCATEGORIES = ("Cargo no reconocido", "Cobro indebido")
DUR = "try_cast(duration_seconds as double)"
WAIT = "try_cast(wait_time_seconds as double)"


def m(value, n) -> dict:
    if isinstance(value, float):
        value = round(value, 6)
    return {"value": value, "n": int(n or 0)}


def _b(col: str) -> str:
    return f"({col} = 'True')::int"


def _rows(c, sql: str) -> list[tuple]:
    return c.sql(sql).fetchall()


def demand(c) -> dict:
    total = _rows(c, "select count(*) from interactions")[0][0]
    out = {"demand.total": m(total, total)}
    for h, n in _rows(c, "select hour(try_cast(interaction_date as timestamp)), count(*) from interactions group by 1"):
        out[f"demand.by_hour.{int(h):02d}"] = m(n, total)
    for d, n in _rows(c, "select dayname(try_cast(interaction_date as timestamp)), count(*) from interactions group by 1"):
        out[f"demand.by_weekday.{d}"] = m(n, total)
    for ch, n in _rows(c, "select channel, count(*) from interactions group by 1"):
        out[f"demand.by_channel.{ch}"] = m(n / total, total)
    for r, n in _rows(c, "select reason_category, count(*) from interactions group by 1"):
        out[f"demand.by_reason.{r}"] = m(n / total, total)
    for month, n in _rows(c, "select substr(process_date, 1, 7), count(*) from interactions_hist group by 1"):
        out[f"demand.trend.{month}"] = m(n, n)
    inscope = _rows(c, f"select count(*) from interactions where reason_category = '{IN_SCOPE_REASON}'")[0][0]
    disputes = _rows(c, f"select count(*) from complaints where subcategory in {DISPUTE_SUBCATEGORIES!r}")[0][0]
    out["demand.in_scope_interactions_per_month"] = m(inscope / MONTHS_IN_WINDOW, inscope)
    out["demand.dispute_complaints_per_month"] = m(disputes / MONTHS_IN_WINDOW, disputes)
    out["demand.in_scope_per_month"] = m((inscope + disputes) / MONTHS_IN_WINDOW, inscope + disputes)
    return out


def quality(c) -> dict:
    out = {}
    for r, n, fcr, esc, fu, n_dur, h50, h90, n_wait, w50, neg in _rows(c, f"""
            select reason_category, count(*), avg({_b('was_resolved')}), avg({_b('was_escalated')}),
                   avg({_b('requires_followup')}), count({DUR}), quantile_cont({DUR}, 0.5), quantile_cont({DUR}, 0.9),
                   count({WAIT}), quantile_cont({WAIT}, 0.5),
                   avg((detected_sentiment in ('Negative', 'Very Negative'))::int)
            from interactions group by 1"""):
        p = f"quality.{r}"
        out |= {f"{p}.fcr": m(fcr, n), f"{p}.escalation_rate": m(esc, n), f"{p}.followup_rate": m(fu, n),
                f"{p}.handle_time_s_p50": m(h50, n_dur), f"{p}.handle_time_s_p90": m(h90, n_dur),
                f"{p}.wait_time_s_p50": m(w50, n_wait), f"{p}.negative_sentiment_share": m(neg, n)}
    return out


def satisfaction(c) -> dict:
    out = {}
    base = "from surveys s join interactions i using (interaction_id)"
    score = "try_cast(s.main_score as double)"
    for r, st, n, mean in _rows(c, f"select i.reason_category, s.survey_type, count(*), avg({score}) {base} group by 1, 2"):
        out[f"satisfaction.{r}.{st}.mean"] = m(mean, n)
    for r, n, d in _rows(c, f"""select i.reason_category, count(*), avg((s.nps_category = 'Detractor')::int)
                                {base} where s.survey_type = 'NPS' group by 1"""):
        out[f"satisfaction.{r}.nps_detractor_share"] = m(d, n)
    for resolved, n, mean in _rows(c, f"select i.was_resolved, count(*), avg({score}) {base} where s.survey_type = 'CSAT' group by 1"):
        out[f"satisfaction.{'csat_resolved' if resolved == 'True' else 'csat_unresolved'}.mean"] = m(mean, n)
    n, link = _rows(c, """select count(*), avg((interaction_id in (select interaction_id from interactions_hist))::int)
                          from surveys""")[0]
    out["satisfaction.link_rate"] = m(link, n)
    return out


# Shift hours are an assumption (the data has no schedule); the report states it.
SHIFT_HOURS = {"Morning": list(range(6, 14)), "Afternoon": list(range(14, 22)), "Night": [22, 23, 0, 1, 2, 3, 4, 5]}


def capacity(c) -> dict:
    n_agents, pt, load = _rows(c, """select count(*), avg((lower(languages) like '%portugu%')::int),
                                     avg(try_cast(total_monthly_interactions as double)) from agents""")[0]
    out = {"capacity.agents_total": m(n_agents, n_agents), "capacity.pt_agent_share": m(pt, n_agents),
           "capacity.monthly_load_mean": m(load, n_agents)}
    for t, n in _rows(c, "select agent_type, count(*) from agents group by 1"):
        out[f"capacity.by_type.{t}"] = m(n, n_agents)
    shifts = dict(_rows(c, "select work_shift, count(*) from agents group by 1"))
    by_hour = dict(_rows(c, "select hour(try_cast(interaction_date as timestamp)), count(*) from interactions group by 1"))
    for shift, hours in SHIFT_HOURS.items():
        agents = shifts.get(shift, 0)
        contacts = sum(by_hour.get(h, 0) for h in hours)
        out[f"capacity.by_shift.{shift}.agents"] = m(agents, n_agents)
        out[f"capacity.by_shift.{shift}.contacts_per_agent"] = m(contacts / agents if agents else None, contacts)
    return out


def disputes(c) -> dict:
    where = f"where subcategory in {DISPUTE_SUBCATEGORIES!r}"
    fr = ("date_diff('minute', try_cast(creation_date as timestamp), try_cast(first_response_date as timestamp))"
          " / 60.0")
    res = "try_cast(resolution_days as double)"
    n, n_fr, fr50, n_res, res50, sla, backlog = _rows(c, f"""
        select count(*), count({fr}), quantile_cont({fr}, 0.5), count({res}), quantile_cont({res}, 0.5),
               avg({_b('sla_breached')}), avg((status in ('Open', 'In Process'))::int) from complaints {where}""")[0]
    total = _rows(c, "select count(*) from complaints")[0][0]
    out = {"complaints.total": m(total, total), "disputes.count": m(n, n),
           "disputes.first_response_h_p50": m(fr50, n_fr), "disputes.resolution_days_p50": m(res50, n_res),
           "disputes.sla_breach_rate": m(sla, n), "disputes.backlog_share": m(backlog, n)}
    for ch, k in _rows(c, f"select reception_channel, count(*) from complaints {where} group by 1"):
        out[f"disputes.by_channel.{ch}"] = m(k / n, n)
    for sub, k in _rows(c, f"select subcategory, count(*) from complaints {where} group by 1"):
        out[f"disputes.by_subcategory.{sub}"] = m(k, n)
    return out


def digital(c) -> dict:
    return {f"digital.monthly.{et}": m(n / MONTHS_IN_WINDOW, n)
            for et, n in _rows(c, "select event_type, count(*) from digital group by 1")}


def transcripts(c) -> dict:
    n, distinct, cg = _rows(c, """select count(*), count(distinct customer_text),
                                  avg((coalesce(detected_intents, '') like '%consulta_general%')::int) from transcripts""")[0]
    return {"transcripts.rows": m(n, n), "transcripts.distinct_customer_text": m(distinct, n),
            "transcripts.consulta_general_share": m(cg, n)}


def fairness(c) -> dict:
    out = {}
    dur = "try_cast(i.duration_seconds as double)"
    base = f"from interactions i left join customers k using (customer_id) where i.reason_category = '{IN_SCOPE_REASON}'"
    dims = {"country": "k.country", "segment": "k.segment", "accent": "coalesce(i.customer_detected_accent, 'unknown')"}
    for dim, expr in dims.items():
        for val, n, fcr, n_dur, h50 in _rows(c, f"""select {expr}, count(*), avg({_b('i.was_resolved')}), count({dur}),
                                                     quantile_cont({dur}, 0.5) {base} group by 1"""):
            out[f"fairness.by_{dim}.{val}.fcr"] = m(fcr, n)
            out[f"fairness.by_{dim}.{val}.handle_time_s_p50"] = m(h50, n_dur)
    for val, n, csat in _rows(c, f"""select k.country, count(*), avg(try_cast(s.main_score as double))
                                     from surveys s join interactions i using (interaction_id)
                                     left join customers k on k.customer_id = i.customer_id
                                     where i.reason_category = '{IN_SCOPE_REASON}' and s.survey_type = 'CSAT'
                                     group by 1"""):
        out[f"fairness.by_country.{val}.csat_mean"] = m(csat, n)
    return out


def collect(c) -> dict:
    out = {}
    for fn in (demand, quality, satisfaction, capacity, disputes, digital, transcripts, fairness):
        out |= fn(c)
    return dict(sorted(out.items()))
