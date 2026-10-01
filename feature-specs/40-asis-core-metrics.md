# 40 · As-Is Project, Loader and Core Metrics

**Subsystem:** Evaluation · **Depends on:** none · **Reference:** evaluation plan, Task 1

## Goal

Create the `analysis/` as-is project: DuckDB views over the raw drop (normalized like staging) and the demand, quality and satisfaction metrics.

## Read First

- `context/ai-workflow-rules.md` and `context/progress-tracker.md` (always)
- `context/code-standards.md` → Evaluation

## Requirements

Copied word for word from the design specs. Architecture Decisions in `progress-tracker.md` override this text where they conflict.

### Facts this design rests on · evaluation §2

Profiled from `data/data/` on 2026-10-01, window: `process_date` in [2025-06-17, 2026-06-17].

**Contact center (`call_center_interactions`, 230,196 rows in the window):**

| reason_category | n | FCR | escalated | follow-up | median handle | median wait |
|---|---|---|---|---|---|---|
| Transaccional | 80,264 | 91.6% | 10.0% | 22.0% | 3.4 min | 2.0 min |
| Producto | 50,602 | 89.7% | 10.0% | 23.7% | 4.4 min | 2.0 min |
| Queja | 39,300 | 43.6% | 10.0% | 62.8% | 7.2 min | 2.0 min |
| Técnico | 34,590 | 69.7% | 10.3% | 40.7% | 6.0 min | 2.0 min |
| Comercial | 18,552 | 65.4% | 9.8% | 44.3% | 9.0 min | 2.0 min |
| Retención | 6,888 | 60.2% | 9.3% | 49.3% | 8.0 min | 2.0 min |

- Channels: Phone 85% (inbound 161k, outbound 34k), Email 4%, chat (App, WhatsApp, Web Chat) 10%, video under 1%.
- Demand is flat by hour (about 9.4k–9.8k per hour of day, all 24 hours) and lower on weekends (Sunday about half of Wednesday). Monthly volume is stable at about 19k.
- `Transaccional` sentiment is 100% `Neutral`; other categories mix.
- FCR is the same by accent (76.6–76.8%).
- Repeat contact for the same reason within 7 days: 0.2–1.0%.

**Surveys (`satisfaction_surveys`):** 100% link to an interaction. CSAT 42,608, NPS 21,538, CES 7,213 in the window. CSAT is exactly 3.00 when the interaction was resolved and 2.00 when not, regardless of escalation. NPS detractor share 69–86% by reason.

**Agents (`service_agents`, 1,200):** 129 (10.8%) list Portuguese. Average monthly interactions about 410–540 per agent by type. Columns `work_shift`, `specialty`, `languages`, `avg_csat` are available; names, emails and phones are not used.

**Complaints (window, 22,552):** top subcategories *Cargo no reconocido* 4,193 and *Cobro indebido* 4,006. Median first response 37 h, median resolution 15–16 days, SLA breach 17–21% in every subcategory. Reception channel: Call Center 50%, Email 20%, Web 15%, App 10%, Branch 4%, Regulator 1%. Status: In Process 40%, Open 30%, Resolved 21%, Escalated 5%, Closed 4%, Rejected 1%.

**Digital events (May 2026 sample):** logins about 66k per month; transaction form submits 16k; error events about 9.7k (transaction and navigation).

**Transcripts:** unusable as labels (resolver spec §2: 42 distinct customer texts, intents almost all `consulta_general`).

**Synthetic artifacts** (reported, never used as argument for the new system): escalation about 10% in every slice, SLA breach about 20% in every slice, wait time constant at 2.0 min, CSAT determined by `was_resolved`, `Transaccional` sentiment constant, no Portuguese-speaking customers.

### Inputs and rules · evaluation §3.1

- Reads `data/data/` only; `data_backup_20260831/` is never read (pipeline spec §2).
- Same normalizations as pipeline staging (pipeline spec §5.2): sentiment mapped to English, empty strings to null, UTF-8 BOM skipped, `process_date` from the partition.
- Window for every rate: `process_date` in [2025-06-17, 2026-06-17]. The full 2023-06-17 → 2026-06-17 history is used only for trend charts.
- PII columns (names, documents, emails, phones, addresses) are never selected.

### Questions answered (this unit: 1–2)

*From evaluation §3.2 (items 3–8 are unit 41):*

Each finding is tagged **evidence** or **synthetic artifact** (§2).

1. **Demand.** Volume by reason, channel, hour, weekday and month. The in-scope share: `Transaccional` interactions plus complaints in *Cargo no reconocido* and *Cobro indebido*.
2. **Service quality.** FCR, escalation, follow-up, handle time, wait time and sentiment by reason. CSAT, CES and NPS by reason and by resolved/unresolved through the survey→interaction link.

## Implementation

### Files

- Create: `analysis/pyproject.toml`, `analysis/asis/__init__.py`, `analysis/asis/load.py`, `analysis/asis/metrics.py`, `analysis/asis/tests/__init__.py`, `analysis/asis/tests/fixtures.py`, `analysis/asis/tests/conftest.py`, `analysis/asis/tests/test_core_metrics.py`

### Interfaces

- Consumes: the raw drop layout (`<table>/year=/month=/day=/<table>_YYYYMMDD.csv`, `customers.csv`, `service_agents.csv`).
- Produces:
  - `asis.load`: `WINDOW = ("2025-06-17", "2026-06-17")`, `MONTHS_IN_WINDOW = 12`, `connect(data_dir: Path, window=WINDOW) -> duckdb.DuckDBPyConnection` with views `interactions_hist`, `interactions`, `surveys`, `complaints`, `digital`, `transcripts`, `customers`, `agents`;
  - `asis.metrics`: `m(value, n) -> dict`, `IN_SCOPE_REASON`, `DISPUTE_SUBCATEGORIES`, `demand(c)`, `quality(c)`, `satisfaction(c)`, each returning `dict[str, {"value", "n"}]`;
  - `asis.tests.fixtures.write_fixture(root: Path) -> Path`.

## Scope Limits

- `analysis/asis/load.py`, `metrics.py` (core groups) and tests on a labeled synthetic CSV fixture. Keep the existing profiling scripts in `analysis/` untouched.
- Never read `data_backup_20260831/`; never select PII columns.
- Don't touch files outside this unit's list, except to fix a bug in an earlier unit (with a test).

## Check When Done

- The reference task's tests exist and pass:
  `test_quality_uses_the_window_and_matches_hand_counts`, `test_spanish_sentiment_labels_are_normalized`, `test_demand`, `test_satisfaction_through_the_survey_link`, `test_backup_prefix_is_refused`, `test_customer_pii_columns_are_not_exposed`
- The subsystem's offline suite still passes.
- `context/progress-tracker.md` is updated, and the unit is committed alone.

## Reference (open only if needed)

Read only this line range, and only for exact code, test bodies or commands:

`docs/reference/plans/2026-10-01-evaluation.md`: Task 1 (As-is project, fixture, loader and core metrics), lines 70–469
