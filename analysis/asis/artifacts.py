"""Synthetic-artifact detectors (evaluation spec §2, §3.2 item 7). A finding backed by a detector that holds is tagged
"synthetic artifact" and is never used to argue for the new system."""


def _a(name: str, holds: bool, evidence: str, query: str) -> dict:
    return {"name": name, "holds": bool(holds), "evidence": evidence, "query": " ".join(query.split())}


def _range_detector(c, name, query, max_range, label):
    rates = [r[-1] for r in c.sql(query).fetchall() if r[-1] is not None]
    if len(rates) < 2:
        return _a(name, False, "insufficient data: fewer than 2 buckets with enough rows", query)
    spread = max(rates) - min(rates)
    return _a(name, spread < max_range, f"{len(rates)} {label} buckets; range {spread:.3f}", query)


def escalation_flat(c, min_n=1000, max_range=0.02):
    q = f"""select reason_category, channel, avg((was_escalated = 'True')::int) from interactions
            group by all having count(*) >= {min_n}"""
    return _range_detector(c, "escalation_flat", q, max_range, "reason x channel")


def sla_flat(c, min_n=500, max_range=0.06):
    q = f"""select category, priority, avg((sla_breached = 'True')::int) from complaints
            group by all having count(*) >= {min_n}"""
    return _range_detector(c, "sla_flat", q, max_range, "category x priority")


def wait_constant(c, max_spread_s=30):
    q = """select quantile_cont(try_cast(wait_time_seconds as double), 0.1),
                  quantile_cont(try_cast(wait_time_seconds as double), 0.9) from interactions"""
    p10, p90 = c.sql(q).fetchone()
    if p10 is None:
        return _a("wait_constant", False, "insufficient data: no wait times", q)
    return _a("wait_constant", (p90 - p10) <= max_spread_s, f"wait p10 {p10:.0f}s, p90 {p90:.0f}s", q)


def csat_by_resolution(c, min_n=1000, max_range=0.05):
    q = f"""select i.was_resolved, i.reason_category, avg(try_cast(s.main_score as double))
            from surveys s join interactions i using (interaction_id) where s.survey_type = 'CSAT'
            group by all having count(*) >= {min_n}"""
    groups: dict[str, list[float]] = {}
    for resolved, _, mean in c.sql(q).fetchall():
        groups.setdefault(resolved, []).append(mean)
    usable = {k: v for k, v in groups.items() if len(v) >= 2}
    if not usable:
        return _a("csat_by_resolution", False, "insufficient data: no resolution status with 2 reasons", q)
    spreads = {k: max(v) - min(v) for k, v in usable.items()}
    evidence = "; ".join(f"was_resolved={k}: CSAT range across reasons {s:.3f}" for k, s in sorted(spreads.items()))
    return _a("csat_by_resolution", all(s < max_range for s in spreads.values()), evidence, q)


def transactional_sentiment_constant(c):
    q = """select detected_sentiment, count(*) from interactions where reason_category = 'Transaccional'
           group by 1 order by 2 desc"""
    rows = c.sql(q).fetchall()
    total = sum(n for _, n in rows)
    if not total:
        return _a("transactional_sentiment_constant", False, "insufficient data", q)
    top, n = rows[0]
    return _a("transactional_sentiment_constant", n / total >= 0.99, f"{top} is {n / total:.1%} of {total:,}", q)


def no_pt_customers(c):
    q = "select country, count(*) from customers group by 1 order by 2 desc"
    rows = c.sql(q).fetchall()
    pt = sum(n for country, n in rows if country in ("Brasil", "Brazil", "Portugal"))
    return _a("no_pt_customers", pt == 0, "countries: " + ", ".join(f"{k} {n:,}" for k, n in rows), q)


def transcripts_templated(c, max_ratio=0.01):
    q = "select count(*), count(distinct customer_text) from transcripts"
    n, distinct = c.sql(q).fetchone()
    if not n:
        return _a("transcripts_templated", False, "insufficient data", q)
    return _a("transcripts_templated", distinct / n < max_ratio, f"{distinct:,} distinct texts in {n:,} rows", q)


def detect_all(c) -> list[dict]:
    return [escalation_flat(c), sla_flat(c), wait_constant(c), csat_by_resolution(c),
            transactional_sentiment_constant(c), no_pt_customers(c), transcripts_templated(c)]
