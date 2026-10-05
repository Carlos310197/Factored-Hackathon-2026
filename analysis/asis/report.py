"""Markdown for reports/asis-<date>.md (evaluation spec §3.2). Numbers come only from the metrics dict."""


def _v(metrics: dict, key: str, fmt: str = "{:.1%}") -> str:
    x = metrics.get(key)
    if not x or x["value"] is None:
        return "n/a"
    return f"{fmt.format(x['value'])} (n={x['n']:,})"


def render(metrics: dict, artifacts: list[dict], recon: dict, date: str, figures: list[str]) -> str:
    arts = {a["name"]: a for a in artifacts}

    def tag(name: str) -> str:
        return "synthetic artifact" if arts.get(name, {}).get("holds") else "evidence"

    def v(key: str, fmt: str = "{:.1%}") -> str:
        return _v(metrics, key, fmt)

    reasons = sorted({k.split(".")[1] for k in metrics if k.startswith("quality.") and k.endswith(".fcr")},
                     key=lambda r: -metrics[f"quality.{r}.fcr"]["n"])
    hours = [x["value"] for k, x in metrics.items() if k.startswith("demand.by_hour.")]
    L = ["# As-is diagnosis of the LATAM Bank contact center", "",
         f"Generated {date} from `data/data/`, window 2025-06-17 → 2026-06-17 (inclusive). Every finding is tagged "
         f"**evidence** or **synthetic artifact**; synthetic artifacts are reported but never used to argue for the "
         f"new system. Reconciliation with the curated marts: **{recon['status']}**.", ""]
    L += ["## 1. Demand", "",
          f"- In-scope contacts per month (Transaccional interactions plus dispute complaints): "
          f"{v('demand.in_scope_per_month', '{:,.0f}')} · evidence",
          f"- Phone share of all contacts: {v('demand.by_channel.Phone')} · evidence"]
    if hours:
        L.append(f"- Contacts per hour of day range from {min(hours):,} to {max(hours):,}: flat across the day and night, "
                 f"which a real contact center doesn't show (uniform generator) · synthetic artifact")
    L += ["", "| Reason | Share of contacts |", "|---|---|"]
    L += [f"| {r} | {v(f'demand.by_reason.{r}')} |" for r in reasons]
    L += ["", "## 2. Service quality today", "",
          "| Reason | FCR | Escalated | Follow-up | Handle p50 (s) | Handle p90 (s) | Wait p50 (s) | Negative sentiment |",
          "|---|---|---|---|---|---|---|---|"]
    L += [f"| {r} | {v(f'quality.{r}.fcr')} | {v(f'quality.{r}.escalation_rate')} | {v(f'quality.{r}.followup_rate')} | "
          f"{v(f'quality.{r}.handle_time_s_p50', '{:,.0f}')} | {v(f'quality.{r}.handle_time_s_p90', '{:,.0f}')} | "
          f"{v(f'quality.{r}.wait_time_s_p50', '{:,.0f}')} | {v(f'quality.{r}.negative_sentiment_share')} |"
          for r in reasons]
    L += ["",
          f"- Escalation rate · {tag('escalation_flat')}: {arts.get('escalation_flat', {}).get('evidence', '')}",
          f"- Wait time · {tag('wait_constant')}: {arts.get('wait_constant', {}).get('evidence', '')}",
          f"- CSAT resolved {v('satisfaction.csat_resolved.mean', '{:.2f}')} vs unresolved "
          f"{v('satisfaction.csat_unresolved.mean', '{:.2f}')} · {tag('csat_by_resolution')}: "
          f"{arts.get('csat_by_resolution', {}).get('evidence', '')}",
          f"- Transaccional sentiment · {tag('transactional_sentiment_constant')}: "
          f"{arts.get('transactional_sentiment_constant', {}).get('evidence', '')}",
          f"- Surveys linked to an interaction: {v('satisfaction.link_rate')} · evidence"]
    L += ["", "## 3. Capacity", "",
          f"- Agents: {v('capacity.agents_total', '{:,}')}; listing Portuguese: {v('capacity.pt_agent_share')} · evidence",
          f"- Agents' `total_monthly_interactions` attribute averages {v('capacity.monthly_load_mean', '{:,.0f}')} · "
          f"synthetic artifact: it does not reconcile with the logged contacts",
          f"- Logged contacts per agent per month: {v('capacity.observed_monthly_per_agent', '{:,.1f}')} · evidence", "",
          "| Shift (assumed hours) | Agents | Contacts per agent in the window |", "|---|---|---|"]
    L += [f"| {s} | {v(f'capacity.by_shift.{s}.agents', '{:,}')} | "
          f"{v(f'capacity.by_shift.{s}.contacts_per_agent', '{:,.1f}')} |" for s in ("Morning", "Afternoon", "Night")]
    L += ["", "Shift hours are an assumption (Morning 06–13, Afternoon 14–21, Night 22–05); the data has no schedule. "
               "The per-shift load comes from flat hourly demand and these assumed hours, so it is not evidence."]
    L += ["", "## 4. Dispute handling today", "",
          f"- Dispute complaints (Cargo no reconocido, Cobro indebido): {v('disputes.count', '{:,}')}",
          f"- Median time to first response: {v('disputes.first_response_h_p50', '{:,.1f} h')} · evidence",
          f"- Median time to resolution: {v('disputes.resolution_days_p50', '{:,.1f} days')} · evidence",
          f"- SLA breached: {v('disputes.sla_breach_rate')} · {tag('sla_flat')}: "
          f"{arts.get('sla_flat', {}).get('evidence', '')}",
          f"- Still Open or In Process: {v('disputes.backlog_share')} · evidence"]
    L += [f"- Received through {k.rsplit('.', 1)[1]}: {v(k)}" for k in sorted(metrics)
          if k.startswith("disputes.by_channel.")]
    L += ["", "## 5. Digital channel", "", "Descriptive only."]
    L += [f"- {k.rsplit('.', 1)[1]} events per month: {v(k, '{:,.0f}')}" for k in sorted(metrics)
          if k.startswith("digital.monthly.")]
    L += ["", "## 6. Unusable sources", "",
          f"- Transcripts: {v('transcripts.distinct_customer_text', '{:,}')} distinct customer texts; "
          f"{v('transcripts.consulta_general_share')} tagged `consulta_general` · {tag('transcripts_templated')}. "
          f"They are not used as labels."]
    L += ["", "## 7. Data limits and synthetic artifacts", "", "| Check | Holds | Evidence |", "|---|---|---|"]
    L += [f"| {a['name']} | {'yes' if a['holds'] else 'no'} | {a['evidence']} |" for a in artifacts]
    L += ["", "## 8. Fairness reference", "", "Transaccional interactions only.", "",
          "| Dimension | Value | FCR | Handle p50 (s) |", "|---|---|---|---|"]
    for k in sorted(metrics):
        if k.startswith("fairness.by_") and k.endswith(".fcr"):
            _, dim, val, _ = k.split(".", 3)
            L.append(f"| {dim.removeprefix('by_')} | {val} | {v(k)} | "
                     f"{v(f'fairness.{dim}.{val}.handle_time_s_p50', '{:,.0f}')} |")
    L += ["", "## Figures", ""] + [f"![{f}](figures/{f})" for f in figures]
    return "\n".join(L) + "\n"
