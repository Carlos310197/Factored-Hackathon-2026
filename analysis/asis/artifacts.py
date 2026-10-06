"""Synthetic-artifact detectors. A finding backed by a detector that holds is tagged
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
    """Escalation is about 10% in every slice. Slices are contact reasons; reason x channel buckets are
    too small to be read as flat (sampling noise alone exceeds the limit)."""
    q = f"""select reason_category, avg((was_escalated = 'True')::int) from interactions
            group by all having count(*) >= {min_n}"""
    return _range_detector(c, "escalation_flat", q, max_range, "reason")


def sla_flat(c, min_n=500, max_range=0.06):
    q = f"""select category, priority, avg((sla_breached = 'True')::int) from complaints
            group by all having count(*) >= {min_n}"""
    return _range_detector(c, "sla_flat", q, max_range, "category x priority")


def wait_constant(c, max_spread_s=30):
    """The median wait is 2.0 min in every slice. The per-slice medians are compared; the p10-p90 spread
    of individual waits is reported but does not decide."""
    q = """select reason_category, channel, quantile_cont(try_cast(wait_time_seconds as double), 0.5),
                  quantile_cont(try_cast(wait_time_seconds as double), 0.1),
                  quantile_cont(try_cast(wait_time_seconds as double), 0.9)
           from interactions group by all"""
    rows = [r for r in c.sql(q).fetchall() if r[2] is not None]
    if not rows:
        return _a("wait_constant", False, "insufficient data: no wait times", q)
    medians = [r[2] for r in rows]
    spread = max(medians) - min(medians)
    evidence = (f"{len(rows)} reason x channel slices; median wait {min(medians):.0f}-{max(medians):.0f}s "
                f"(spread {spread:.0f}s); individual waits p10 {min(r[3] for r in rows):.0f}s, "
                f"p90 {max(r[4] for r in rows):.0f}s")
    return _a("wait_constant", spread <= max_spread_s, evidence, q)


def csat_by_resolution(c, min_n=1000, max_within_share=0.15):
    """CSAT is determined by was_resolved. Holds when the resolved-unresolved gap is large against how much
    CSAT still varies across contact reasons within one resolution status."""
    q = f"""select i.was_resolved, i.reason_category, avg(try_cast(s.main_score as double))
            from surveys s join interactions i using (interaction_id) where s.survey_type = 'CSAT'
            group by all having count(*) >= {min_n}"""
    groups: dict[str, list[float]] = {}
    for resolved, _, mean in c.sql(q).fetchall():
        groups.setdefault(resolved, []).append(mean)
    usable = {k: v for k, v in groups.items() if len(v) >= 2}
    if not usable or not {"True", "False"} <= groups.keys():
        return _a("csat_by_resolution", False,
                  "insufficient data: need both resolution statuses and at least one with 2 reasons", q)
    spread = max(max(v) - min(v) for v in usable.values())
    centre = {k: sum(v) / len(v) for k, v in groups.items()}
    gap = centre["True"] - centre["False"]
    evidence = (f"mean CSAT resolved {centre['True']:.2f} vs unresolved {centre['False']:.2f} (gap {gap:.2f}); "
                f"largest range across reasons within a status {spread:.3f}")
    return _a("csat_by_resolution", gap > 0 and spread <= max_within_share * gap, evidence, q)


def transactional_sentiment_constant(c):
    q = """select detected_sentiment, count(*) from interactions where reason_category = 'Transaccional'
           group by 1 order by 2 desc, 1"""
    rows = c.sql(q).fetchall()
    total = sum(n for _, n in rows)
    if not total:
        return _a("transactional_sentiment_constant", False, "insufficient data", q)
    top, n = rows[0]
    return _a("transactional_sentiment_constant", n / total >= 0.99, f"{top} is {n / total:.1%} of {total:,}", q)


def no_pt_customers(c):
    q = "select country, count(*) from customers group by 1 order by 2 desc, 1"
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
