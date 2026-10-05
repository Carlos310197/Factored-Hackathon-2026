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
