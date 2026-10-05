import { describe, expect, it } from "vitest";
import type { ChatMessage } from "@/lib/contract";
import type { DecisionRecord } from "@/lib/server/records";
import { BELOW_COLOR, signalColor } from "@/lib/trace/signals";
import { buildTrace, buildTurn } from "@/lib/trace/viewModel";

const TH = { intent: 0.8, "intent.margin": 0.15, target_transaction: 0.85, "target_transaction.margin": 0.2, confirmation: 0.9,
  injection_attempt: 0.5, reports_unauthorized_use: 0.5, legal_or_regulator_threat: 0.5, asks_for_human: 0.6, distress: 0.6 };
let seq = 0;
const rec = (turn: string, node: string, kind: string, payload: Record<string, unknown>, versions = {}): DecisionRecord =>
  ({ session_id: "S-1", sk: `${turn}#${String(++seq).padStart(4, "0")}`, turn_id: turn, seq, node, kind, ts: "t", payload, versions });
const customer = (turn: string, text: string): ChatMessage => ({ id: `m-${turn}`, cursor: "c", role: "customer", text, turn_id: turn, ts: "t" });

function unauthorizedTurn() {
  return [
    rec("T2", "understand", "llm", { role: "extract", output: { english_gloss: "I don't recognize a $420 Amazon charge" } }),
    rec("T2", "understand", "model", { probs: { "TRX-7": 0.82, "TRX-3": 0.07, "TRX-12": 0.03 },
      contributions: { "TRX-7": [["amount_log_err", 1.9], ["merchant_sim", 1.4], ["date_in_range", 0.6]] } }),
    rec("T2", "understand", "jev", { thresholds: TH,
      aliases: { c7: { transaction_id: "TRX-7", merchant: "Amazon", amount: 420, currency: "USD", date: "2026-06-02" },
        c3: { transaction_id: "TRX-3", merchant: "Uber", amount: 12, currency: "USD", date: "2026-06-01" } },
      answers: {
        intent: { label: "dispute_charge", probabilities: { dispute_charge: 0.93, transaction_status: 0.04, unclear: 0.03 } },
        target_transaction: { label: "c7", probabilities: { c7: 0.91, c3: 0.05, ambiguous: 0.04 } },
        dispute_reason: { label: "unauthorized", probabilities: { unauthorized: 0.95, unclear: 0.05 } },
        asks_for_human: { p: 0.06 }, reports_unauthorized_use: { p: 0.88 }, legal_or_regulator_threat: { p: 0.04 },
        distress: { p: 0.11 }, injection_attempt: { p: 0.01 } } },
      { question_set: "understand.v1", thresholds: "thresholds.v1" }),
    rec("T2", "understand", "route", { next: "resolve_transaction", reasons: ["reports_unauthorized_use"] }),
    rec("T2", "check_eligibility", "policy", { outcome: "human_review", rules: [
      { name: "within_60_days", passed: true, detail: "" }, { name: "automated_eligible", passed: false, detail: "unauthorized" },
      { name: "fraud_score_ok", passed: false, detail: "61" }] }),
    rec("T2", "handoff", "tool", { handoff_id: "HND-7Q2K", priority: "critical", reason_codes: ["reports_unauthorized_use"] }),
    rec("T2", "reply", "llm", { role: "compose", claims: [{}, {}] }),
    rec("T2", "reply", "jev", { verify: { ok: true, failed_claims: [], promises_unverified: false } }),
    rec("T2", "turn", "turn_end", { duration_ms: 2400, awaiting: "none" }),
  ];
}

describe("buildTurn", () => {
  it("opens crossed flags first, then path choices, capped at 4, and folds the rest", () => {
    const t = buildTurn(unauthorizedTurn(), customer("T2", "No reconozco un cargo de $420 en Amazon"));
    expect(t.bars.map((b) => b.signal)).toEqual(["reports_unauthorized_use", "intent", "target_transaction", "dispute_reason"]);
    expect(t.bars).toHaveLength(4);
    expect(t.folded.count).toBe(4);
    expect(t.folded.highest).toEqual({ label: "Distress", value: 0.11 });
    expect(t.quote).toBe("No reconozco un cargo de $420 en Amazon");
    expect(t.quoteEn).toBe("I don't recognize a $420 Amazon charge");
    expect(t.durationMs).toBe(2400);
  });
  it("colours by signal above the threshold and grey below", () => {
    const t = buildTurn(unauthorizedTurn(), undefined);
    const flag = t.bars[0];
    expect(flag).toMatchObject({ crossed: true, color: signalColor("reports_unauthorized_use"), threshold: 0.5, value: 0.88 });
    expect(flag.verdict).toEqual({ icon: "⚑", text: "handoff" });
    const distress = t.folded.bars.find((b) => b.signal === "distress")!;
    expect(distress).toMatchObject({ crossed: false, color: BELOW_COLOR });
  });
  it("explains choice bars with runner-up, margin and the resolver's candidates", () => {
    const t = buildTurn(unauthorizedTurn(), undefined);
    const intent = t.bars.find((b) => b.signal === "intent")!;
    expect(intent.detail).toBe("dispute_charge · runner-up transaction_status 0.04 · margin 0.89");
    const target = t.bars.find((b) => b.signal === "target_transaction")!;
    expect(target.label).toBe("Target · Amazon USD 420.00");
    expect(target.candidates?.[0]).toEqual({ alias: "c7", label: "Amazon USD 420.00", score: 0.82,
      why: ["amount_log_err", "merchant_sim", "date_in_range"] });
  });
  it("puts failed policy rules first and reads priority from the handoff", () => {
    const t = buildTurn(unauthorizedTurn(), undefined);
    expect(t.route.next).toBe("handoff");
    expect(t.route.priority).toBe("critical");
    expect(t.route.policy.map((p) => p.passed)).toEqual([false, false, true]);
  });
  it("summarises the reply check", () => {
    expect(buildTurn(unauthorizedTurn(), undefined).replyCheck).toEqual(
      { text: "Reply check 2/2 claims supported · no unverified promises", failed: false, regenerated: 0, template: false });
  });
  it("marks an intent below threshold as clarify and colours it grey", () => {
    const recs = [rec("T3", "understand", "jev", { thresholds: TH, aliases: {}, answers: {
      intent: { label: "dispute_charge", probabilities: { dispute_charge: 0.62, decline_explanation: 0.31, unclear: 0.07 } },
      asks_for_human: { p: 0.06 } } }), rec("T3", "understand", "route", { next: "clarify", reasons: [] })];
    const intent = buildTurn(recs, undefined).bars.find((b) => b.signal === "intent")!;
    expect(intent).toMatchObject({ crossed: false, color: BELOW_COLOR, verdict: { icon: "?", text: "below → clarify" } });
  });
  it("turn with only error records renders error rows and route", () => {
    const recs = [rec("T4", "understand", "error", { role: "jev", error: "timeout" }),
      rec("T4", "understand", "route", { next: "clarify", reasons: ["jev_failure"] }),
      rec("T4", "reply", "template", { goal: "ask_clarification" })];
    const t = buildTurn(recs, undefined);
    expect(t.bars).toEqual([]);
    expect(t.folded.count).toBe(0);
    expect(t.errors).toEqual(["Jev unavailable → clarify"]);
    expect(t.route.next).toBe("clarify");
    expect(t.replyCheck).toEqual({ text: "Reply check skipped · template reply", failed: true, regenerated: 0, template: true });
  });
  it("counts regenerations and failed claims", () => {
    const recs = [rec("T5", "reply", "llm", { role: "compose", claims: [{}, {}, {}] }),
      rec("T5", "reply", "jev", { verify: { ok: false, failed_claims: [1], promises_unverified: true } }),
      rec("T5", "reply", "llm", { role: "compose", claims: [{}, {}] }),
      rec("T5", "reply", "jev", { verify: { ok: true, failed_claims: [], promises_unverified: false } })];
    expect(buildTurn(recs, undefined).replyCheck).toEqual(
      { text: "Reply check 2/2 claims supported · no unverified promises · regenerated once", failed: false, regenerated: 1, template: false });
  });
});

describe("buildTrace", () => {
  it("groups by turn, newest first, and ignores turns without records", () => {
    const recs = [...unauthorizedTurn(), rec("T9", "understand", "route", { next: "answer_inquiry", reasons: [] })];
    const turns = buildTrace(recs, [customer("T2", "No reconozco…"), customer("T9", "saldo")]);
    expect(turns.map((t) => t.turnId)).toEqual(["T9", "T2"]);
  });
});
