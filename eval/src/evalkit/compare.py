"""Legacy (historical contact center) vs new system, on shared metrics only (spec §5.1), plus the labeled
projection (§5.4). Every row is an offline simulation compared with a historical record."""
from evalkit.metrics import SMALL_N, headline

LABEL = "offline simulation vs historical record; different workloads"
REQUIRED_KEYS = ("quality.Transaccional.fcr", "quality.Transaccional.escalation_rate",
                 "quality.Transaccional.followup_rate", "quality.Transaccional.handle_time_s_p50",
                 "quality.Transaccional.handle_time_s_p90", "quality.Transaccional.wait_time_s_p50",
                 "disputes.first_response_h_p50", "capacity.pt_agent_share", "demand.in_scope_per_month")


class MissingLegacyMetric(KeyError):
    """asis_metrics.json lacks a key the comparison needs."""


def _s(ms):
    return round(ms / 1000, 3) if ms is not None else None


def legacy_cost_per_contact(asis_metrics: dict, cfg: dict) -> dict:
    legacy = (cfg or {}).get("legacy") or {}
    if legacy.get("cost_per_agent_hour_usd") is None or not legacy.get("source"):
        return {"value": "not computed", "reason": "legacy.cost_per_agent_hour_usd needs a value and a source"}
    hours = asis_metrics["quality.Transaccional.handle_time_s_p50"]["value"] / 3600
    return {"value": round(legacy["cost_per_agent_hour_usd"] * hours, 6), "source": legacy["source"],
            "label": "projection"}


def legacy_vs_new(asis: dict, head: dict, cost_new: dict, cfg: dict) -> list[dict]:
    m = asis.get("metrics") or {}
    missing = [k for k in REQUIRED_KEYS if k not in m]
    if missing:
        raise MissingLegacyMetric(f"asis_metrics.json is missing: {', '.join(missing)}")

    def row(metric, legacy, new, note=""):
        return {"metric": metric, "legacy": legacy, "new": new, "note": note, "label": LABEL}

    conv, first, intake = head["latency_conversation_ms"], head["first_turn_ms"], head["dispute_intake_ms"]
    return [
        row("First-contact resolution", m["quality.Transaccional.fcr"], head["safe_automated_resolution"],
            "legacy: was_resolved on Transaccional contacts; new: safe automated resolution over in-scope goals"),
        row("Escalation rate", m["quality.Transaccional.escalation_rate"], head["handoff_rate"],
            f"new: missed {head['missed_transfers']['value']}, unnecessary {head['unnecessary_transfers']['value']}"),
        row("Follow-up needed", m["quality.Transaccional.followup_rate"], head["open_item"],
            "new: handoff, pending_review dispute, or unresolved"),
        row("Handle time (s)", {"p50": m["quality.Transaccional.handle_time_s_p50"]["value"],
                                "p90": m["quality.Transaccional.handle_time_s_p90"]["value"]},
            {"p50": _s(conv["p50"]), "p95": _s(conv["p95"]), "n": conv["n"]}, "new: agent time only, persona excluded"),
        row("Wait for first response (s)", m["quality.Transaccional.wait_time_s_p50"],
            {"p50": _s(first["p50"]), "p95": _s(first["p95"]), "n": first["n"]},
            "legacy wait is constant in the data (synthetic artifact)"),
        row("Dispute intake time", {"hours_p50": m["disputes.first_response_h_p50"]["value"]},
            {"seconds_p50": _s(intake["p50"]), "n": intake["n"]},
            "legacy: complaint creation to first response; new: first message to a verified case number"),
        row("Portuguese service", m["capacity.pt_agent_share"], head["pt_correct_in_pt"],
            "legacy: share of agents listing Portuguese; new: PT goals with a correct outcome in PT"),
        row("Cost per contact (USD)", legacy_cost_per_contact(m, cfg),
            {"per_attempted_case": cost_new.get("per_attempted_case"), "status": cost_new.get("status")},
            "legacy is a projection from an assumed agent cost per hour"),
    ]


def fairness_rows(asis: dict, rows: list[dict]) -> list[dict]:
    m, out = asis.get("metrics") or {}, []
    for dim in ("country", "segment"):
        for val in sorted({r[dim] for r in rows}, key=str):
            h = headline([r for r in rows if r[dim] == val])
            out.append({"dimension": dim, "value": val, "legacy_fcr": m.get(f"fairness.by_{dim}.{val}.fcr"),
                        "new_safe_resolution": h["safe_automated_resolution"], "n": h["scored"],
                        "small_sample": h["scored"] < SMALL_N, "label": LABEL})
    return out


def projected_savings(asis: dict, head: dict, cost_new: dict, cfg: dict) -> dict:
    lc = legacy_cost_per_contact(asis["metrics"], cfg)
    r = head["safe_automated_resolution"]["value"]
    if lc["value"] == "not computed" or cost_new.get("status") != "ok" or r is None:
        return {"status": "not computed", "label": "projection"}
    volume = asis["metrics"]["demand.in_scope_per_month"]["value"]
    monthly = volume * r * (lc["value"] - cost_new["per_attempted_case"])
    return {"status": "ok", "label": "projection", "monthly_usd": round(monthly, 2),
            "inputs": {"in_scope_per_month": volume, "safe_automated_resolution": r,
                       "legacy_cost_per_contact": lc["value"], "new_cost_per_attempted_case": cost_new["per_attempted_case"]}}
