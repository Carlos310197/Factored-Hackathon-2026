"""SYNTHETIC fixture: labeled test data, NOT organizer records."""
import csv
from pathlib import Path

BOM = "﻿"

INTERACTION_COLS = ["interaction_id", "interaction_date", "process_date", "customer_id", "agent_id",
                    "interaction_type", "channel", "contact_reason", "reason_category", "duration_seconds",
                    "wait_time_seconds", "was_resolved", "requires_followup", "detected_sentiment", "sentiment_score",
                    "customer_detected_accent", "agent_used_accent", "was_escalated", "mentioned_products",
                    "has_transcript", "has_recording"]
SURVEY_COLS = ["survey_id", "survey_date", "process_date", "interaction_id", "customer_id", "agent_id", "survey_type",
               "send_channel", "main_score", "nps_category", "question_1_text", "question_1_response",
               "question_2_text", "question_2_response", "question_3_text", "question_3_response", "open_comments",
               "comment_sentiment", "response_time_hours", "campaign_response_rate"]
COMPLAINT_COLS = ["complaint_id", "creation_date", "process_date", "customer_id", "case_type", "category",
                  "subcategory", "reception_channel", "affected_product_id", "related_branch_id",
                  "origin_interaction_id", "description", "claimed_amount", "currency", "priority", "status",
                  "assigned_agent_id", "assignment_date", "first_response_date", "resolution_date", "closing_date",
                  "sla_breached", "resolution_days", "resolution", "compensation_granted", "resolution_satisfaction",
                  "is_repeat_complainer"]
AGENT_COLS = ["agent_id", "employee_code", "first_name", "last_name", "email", "phone", "native_accent",
              "country_of_origin", "assigned_branch_id", "agent_type", "experience_level", "languages", "specialty",
              "hire_date", "avg_csat", "total_monthly_interactions", "agent_status", "work_shift"]
CUSTOMER_COLS = ["customer_id", "document_number", "document_type", "first_name", "last_name", "date_of_birth",
                 "gender", "email", "mobile_phone", "landline_phone", "address", "city", "state", "country",
                 "postal_code", "detected_accent", "segment", "credit_score", "estimated_monthly_income",
                 "occupation", "marital_status", "education_level", "registration_date", "registration_branch_id",
                 "customer_status", "last_updated", "accepts_marketing"]
DIGITAL_COLS = ["event_id", "event_date", "process_date", "customer_id", "session_id", "event_type", "event_category",
                "channel", "platform", "browser", "app_version", "page_url", "page_title", "action", "element_id",
                "product_id", "event_value", "duration_seconds", "ip_address", "ip_country", "ip_city", "is_mobile",
                "referrer", "utm_source", "utm_medium", "utm_campaign"]
TRANSCRIPT_COLS = ["transcript_id", "interaction_id", "process_date", "customer_id", "agent_id", "full_text",
                   "customer_text", "agent_text", "detected_language", "detected_accent", "accent_confidence",
                   "detected_keywords", "mentioned_entities", "detected_intents", "main_topics",
                   "transcription_model", "audio_quality", "duration_seconds"]


def _i(iid, ts, cust, channel, itype, reason, dur, resolved, followup, sentiment, accent, escalated, day="2026-06-10"):
    return [iid, f"{day} {ts}", day, cust, "AGT-FIX1", itype, channel, reason, reason, dur, 120, resolved, followup,
            sentiment, "0.0", accent, "mexican", escalated, "", "False", "False"]


INTERACTIONS = {
    "2026-06-10": [
        _i("INT-FIX1", "09:05:00", "CLI-FIX1", "Phone", "Inbound Call", "Transaccional", 120, "True", "False", "Neutral", "mexican", "False"),
        _i("INT-FIX2", "09:30:00", "CLI-FIX1", "Phone", "Inbound Call", "Transaccional", 180, "True", "True", "Neutral", "mexican", "False"),
        _i("INT-FIX3", "10:00:00", "CLI-FIX2", "Phone", "Inbound Call", "Transaccional", 240, "True", "False", "Neutral", "colombian", "True"),
        _i("INT-FIX4", "23:10:00", "CLI-FIX3", "App", "Chat", "Transaccional", 300, "False", "False", "Neutral", "", "False"),
        _i("INT-FIX5", "11:00:00", "CLI-FIX2", "Phone", "Inbound Call", "Queja", 600, "False", "True", "Negativo", "colombian", "False"),
        _i("INT-FIX6", "12:00:00", "CLI-FIX3", "Phone", "Inbound Call", "Queja", 400, "True", "True", "Muy Negativo", "argentine", "False"),
    ],
    # outside the window: must not move any rate, only the trend
    "2024-01-05": [_i("INT-FIX0", "08:00:00", "CLI-FIX1", "Phone", "Inbound Call", "Transaccional", 900, "False", "False",
                      "Neutral", "mexican", "False", day="2024-01-05")],
}


def _s(sid, iid, cust, stype, score, nps=""):
    return [sid, "2026-06-10 20:00:00", "2026-06-10", iid, cust, "AGT-FIX1", stype, "App", score, nps] + [""] * 10


SURVEYS = [_s("SRV-FIX1", "INT-FIX1", "CLI-FIX1", "CSAT", 3), _s("SRV-FIX2", "INT-FIX2", "CLI-FIX1", "CSAT", 3),
           _s("SRV-FIX3", "INT-FIX4", "CLI-FIX3", "CSAT", 2), _s("SRV-FIX4", "INT-FIX5", "CLI-FIX2", "NPS", 2, "Detractor")]


def _q(qid, cust, cat, sub, channel, first_resp, status, sla, days):
    return [qid, "2026-06-10 10:00:00", "2026-06-10", cust, "Reclamo", cat, sub, channel, "", "", "", "texto", "", "",
            "Media", status, "AGT-FIX1", "2026-06-10 11:00:00", first_resp, "", "", sla, days, "", "False", "3", "False"]


COMPLAINTS = [
    _q("CMP-FIX1", "CLI-FIX1", "Transactions", "Cargo no reconocido", "Call Center", "2026-06-11 22:00:00", "In Process", "False", 15),
    _q("CMP-FIX2", "CLI-FIX2", "Fees", "Cobro indebido", "Email", "2026-06-12 00:00:00", "Open", "True", 16),
    _q("CMP-FIX3", "CLI-FIX3", "Service", "Calidad de servicio", "Web", "2026-06-10 20:00:00", "Resolved", "False", 3),
]


def _a(aid, atype, langs, shift, load):
    return [aid, "E0", "Nombre", "Apellido", "x@example.invalid", "+00", "mexican", "Mexico", "SUC-FIX", atype, "Mid",
            langs, "", "2024-01-01", "4.2", load, "Active", shift]


AGENTS = [_a("AGT-FIX1", "Phone", "español", "Morning", 400), _a("AGT-FIX2", "Phone", "español, portugués", "Afternoon", 500),
          _a("AGT-FIX3", "Digital", "español, inglés", "Night", 600),
          _a("AGT-FIX4", "Hybrid", "español, inglés, portugués", "Morning", 300)]


def _c(cid, country, accent, segment):
    return [cid, "000", "CC", "Nombre", "Apellido", "1990-01-01", "F", "x@example.invalid", "+00", "", "Calle 1",
            "Ciudad", "Estado", country, "00000", accent, segment, "700", "1000", "Empleado", "Soltero",
            "Universitario", "2024-01-01", "SUC-FIX", "Active", "2026-06-01 00:00:00", "True"]


CUSTOMERS = [_c("CLI-FIX1", "México", "mexican", "Retail"), _c("CLI-FIX2", "Colombia", "colombian", "Premium"),
             _c("CLI-FIX3", "Argentina", "argentine", "Retail")]


def _e(eid, etype, cat):
    return [eid, "2026-06-10 10:00:00", "2026-06-10", "CLI-FIX1", "SES-FIX", etype, cat, "App", "iOS"] + [""] * 17


DIGITAL = [_e("EVT-FIX1", "Login", "Authentication"), _e("EVT-FIX2", "Login", "Authentication"),
           _e("EVT-FIX3", "Error", "Transaction"), _e("EVT-FIX4", "Purchase", "Transaction")]


def _t(tid, text, intents):
    return [tid, "INT-FIX1", "2026-06-10", "CLI-FIX1", "AGT-FIX1", text, text, "Claro", "es", "mexican", "0.9", "", "",
            intents, "", "whisper", "good", "120"]


TRANSCRIPTS = [_t("TRS-FIX1", "Quiero saber mi saldo", "consulta_general"),
               _t("TRS-FIX2", "Quiero saber mi saldo", "consulta_general"),
               _t("TRS-FIX3", "Quiero saber mi saldo", "consulta_general"), _t("TRS-FIX4", "Tengo un cargo raro", "")]


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(BOM)
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(["" if v is None else v for v in r] for r in rows)


def _fact(root: Path, table: str, day: str, header: list[str], rows: list[list]) -> None:
    y, mo, d = day.split("-")
    _write(root / table / f"year={y}" / f"month={mo}" / f"day={d}" / f"{table}_{y}{mo}{d}.csv", header, rows)


def write_fixture(root: Path) -> Path:
    for day, rows in INTERACTIONS.items():
        _fact(root, "call_center_interactions", day, INTERACTION_COLS, rows)
    _fact(root, "satisfaction_surveys", "2026-06-10", SURVEY_COLS, SURVEYS)
    _fact(root, "complaints", "2026-06-10", COMPLAINT_COLS, COMPLAINTS)
    _fact(root, "digital_events", "2026-06-10", DIGITAL_COLS, DIGITAL)
    _fact(root, "call_transcripts", "2026-06-10", TRANSCRIPT_COLS, TRANSCRIPTS)
    _write(root / "customers.csv", CUSTOMER_COLS, CUSTOMERS)
    _write(root / "service_agents.csv", AGENT_COLS, AGENTS)
    return root
