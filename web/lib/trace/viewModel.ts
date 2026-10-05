import type { ChatMessage } from "@/lib/contract";
import type { DecisionRecord } from "@/lib/server/records";
import { xrayTraceUrl } from "./xray";
import { BELOW_COLOR, FLAG_KEYS, FLAG_VERDICT, SIGNALS, signalColor, signalOf } from "./signals";

export interface TraceBar {
  signal: string; label: string; value: number; threshold: number | null; crossed: boolean; color: string;
  verdict: { icon: "✓" | "?" | "⚑" | "⛔" | "·"; text: string }; detail?: string;
  candidates?: { alias: string; label: string; score: number; why: string[] }[];
}
export interface TraceTurn {
  turnId: string; quote: string; quoteEn: string | null; durationMs: number | null; bars: TraceBar[];
  folded: { count: number; highest: { label: string; value: number } | null; bars: TraceBar[] };
  replyCheck: { text: string; failed: boolean; regenerated: number; template: boolean } | null;
  errors: string[]; route: { next: string; priority: string | null; policy: { name: string; passed: boolean }[] };
  versions: { questionSet?: string; thresholds?: string }; traceUrl?: string;
}

type Answer = { label: string; probabilities: Record<string, number> } | { p: number };
type Alias = { merchant?: string | null; amount?: number | null; currency?: string | null; transaction_id: string };
const MAX_OPEN = 4;
const r2 = (n: number) => Math.round(n * 100) / 100;
const money = (a: Alias) => `${a.merchant ?? "?"} ${a.currency ?? ""} ${(a.amount ?? 0).toFixed(2)}`.replace(/\s+/g, " ");

const ERROR_TEXT: Record<string, string> = {
  jev: "Jev unavailable → clarify", resolver: "Resolver failed → Jev alone", extract: "Extract failed → Jev on original text",
  compose: "Compose failed → template reply", verify_reply: "Reply check failed → template reply",
  open_questions: "Open questions unavailable → packet without them", handoff: "Handoff write failed → phone channel",
};
const ROUTE_LABEL: Record<string, string> = { resolve_transaction: "dispute", check_eligibility: "dispute" };

function ranked(probs: Record<string, number>) {
  return Object.entries(probs).sort((a, b) => b[1] - a[1]);
}

function choiceBar(key: string, a: { label: string; probabilities: Record<string, number> }, th: Record<string, number>,
  aliases: Record<string, Alias>, model?: DecisionRecord): TraceBar {
  const r = ranked(a.probabilities);
  const value = a.probabilities[a.label] ?? 0;
  const runner = r.find(([k]) => k !== a.label);
  const margin = r2(value - (runner?.[1] ?? 0));
  const threshold = th[key] ?? null;
  const minMargin = th[`${key}.margin`];
  const crossed = threshold === null ? true : value >= threshold && (minMargin === undefined || margin >= minMargin);
  const sig = signalOf(key)!;
  let label: string = sig.label;
  if (key === "target_transaction" && aliases[a.label]) label = `Target · ${money(aliases[a.label])}`;
  const bar: TraceBar = {
    signal: key, label, value: r2(value), threshold, crossed, color: crossed ? sig.color : BELOW_COLOR,
    verdict: crossed ? { icon: "✓", text: threshold === null ? "used" : "act" }
      : { icon: "?", text: key === "confirmation" ? "below → re-ask" : "below → clarify" },
    detail: `${a.label} · runner-up ${runner?.[0] ?? "—"} ${r2(runner?.[1] ?? 0).toFixed(2)} · margin ${margin.toFixed(2)}`,
  };
  if (key === "target_transaction" && model) {
    const probs = (model.payload.probs ?? {}) as Record<string, number>;
    const contrib = (model.payload.contributions ?? {}) as Record<string, [string, number][]>;
    const byTxn = Object.fromEntries(Object.entries(aliases).map(([al, v]) => [v.transaction_id, al]));
    bar.candidates = ranked(probs).slice(0, 3).map(([tid, score]) => ({
      alias: byTxn[tid] ?? tid, label: aliases[byTxn[tid]] ? money(aliases[byTxn[tid]]) : tid, score: r2(score),
      why: (contrib[tid] ?? []).map(([f]) => f),
    }));
  }
  return bar;
}

function flagBar(key: string, p: number, th: Record<string, number>): TraceBar {
  const threshold = th[key] ?? 0.5;
  const crossed = p >= threshold;
  return { signal: key, label: signalOf(key)!.label, value: r2(p), threshold, crossed,
    color: crossed ? signalColor(key) : BELOW_COLOR,
    verdict: crossed ? FLAG_VERDICT[key] : { icon: "·", text: "no effect" } };
}

export function buildTurn(records: DecisionRecord[], customer: ChatMessage | undefined): TraceTurn {
  const recs = [...records].sort((a, b) => a.seq - b.seq);
  const find = (node: string, kind: string) => recs.filter((r) => r.node === node && r.kind === kind);
  const jev = find("understand", "jev").at(-1);
  const model = find("understand", "model").at(-1);
  const answers = (jev?.payload.answers ?? {}) as Record<string, Answer>;
  const th = (jev?.payload.thresholds ?? {}) as Record<string, number>;
  const aliases = (jev?.payload.aliases ?? {}) as Record<string, Alias>;

  const all: TraceBar[] = [];
  for (const s of SIGNALS) {
    const a = answers[s.key];
    if (!a) continue;
    all.push("p" in a ? flagBar(s.key, a.p, th) : choiceBar(s.key, a, th, aliases, model));
  }
  const intentLabel = (answers.intent && "label" in answers.intent) ? answers.intent.label : null;
  const pathChoices = new Set(["intent", "confirmation", ...(intentLabel === "dispute_charge" ? ["target_transaction", "dispute_reason"] : [])]);
  const crossedFlags = all.filter((b) => FLAG_KEYS.includes(b.signal as never) && b.crossed);
  const choices = all.filter((b) => pathChoices.has(b.signal));
  const open = [...crossedFlags, ...choices];
  if (open.length < MAX_OPEN) {
    const closest = all.filter((b) => FLAG_KEYS.includes(b.signal as never) && !b.crossed)
      .sort((a, b) => b.value / (b.threshold ?? 1) - a.value / (a.threshold ?? 1))[0];
    if (closest && closest.value / (closest.threshold ?? 1) >= 0.5) open.push(closest);
  }
  const bars = open.slice(0, MAX_OPEN);
  const foldedBars = all.filter((b) => !bars.includes(b));
  const highest = foldedBars.filter((b) => !b.crossed).sort((a, b) => b.value - a.value)[0];

  const composes = recs.filter((r) => r.node === "reply" && r.kind === "llm" && r.payload.role === "compose");
  const verifies = find("reply", "jev");
  const template = find("reply", "template").length > 0;
  let replyCheck: TraceTurn["replyCheck"] = null;
  if (verifies.length) {
    const v = verifies.at(-1)!.payload.verify as { ok: boolean; failed_claims: number[]; promises_unverified: boolean };
    const n = ((composes.at(-1)?.payload.claims as unknown[]) ?? []).length;
    const regenerated = Math.max(0, composes.length - 1);
    const parts = [`Reply check ${n - v.failed_claims.length}/${n} claims supported`,
      v.promises_unverified ? "unverified promise found" : "no unverified promises"];
    if (regenerated) parts.push(regenerated === 1 ? "regenerated once" : `regenerated ${regenerated} times`);
    if (template) parts.push("template reply");
    replyCheck = { text: parts.join(" · "), failed: !v.ok || template, regenerated, template };
  } else if (template) {
    replyCheck = { text: "Reply check skipped · template reply", failed: true, regenerated: 0, template: true };
  }

  const errors = recs.filter((r) => r.kind === "error").map((r) => {
    const role = String(r.payload.role ?? r.node);
    return ERROR_TEXT[role] ?? `${role}: ${String(r.payload.error ?? "failed")}`;
  });
  const handoffTool = find("handoff", "tool").at(-1);
  const routeRec = find("understand", "route").at(-1);
  const rawNext = handoffTool ? "handoff" : String(routeRec?.payload.next ?? "reply");
  const policyRec = recs.filter((r) => r.kind === "policy").at(-1);
  const policy = ((policyRec?.payload.rules ?? []) as { name: string; passed: boolean }[])
    .map(({ name, passed }) => ({ name, passed })).sort((a, b) => Number(a.passed) - Number(b.passed));
  const extract = recs.find((r) => r.kind === "llm" && r.payload.role === "extract");
  const gloss = (extract?.payload.output as { english_gloss?: string } | undefined)?.english_gloss ?? null;
  const end = recs.find((r) => r.kind === "turn_end");
  const traced = recs.find((r) => typeof r.trace_id === "string" && r.trace_id);
  const traceUrl = traced?.trace_id ? xrayTraceUrl(traced.trace_id) : null;

  return {
    turnId: recs[0]?.turn_id ?? customer?.turn_id ?? "",
    quote: customer?.text ?? "", quoteEn: gloss, durationMs: end ? Number(end.payload.duration_ms) : null,
    bars, folded: { count: foldedBars.length, highest: highest ? { label: highest.label, value: highest.value } : null, bars: foldedBars },
    replyCheck, errors,
    route: { next: ROUTE_LABEL[rawNext] ?? rawNext, priority: handoffTool ? String(handoffTool.payload.priority ?? "") || null : null, policy },
    versions: { questionSet: jev?.versions.question_set, thresholds: jev?.versions.thresholds },
    ...(traceUrl ? { traceUrl } : {}),
  };
}

export function buildTrace(records: DecisionRecord[], messages: ChatMessage[]): TraceTurn[] {
  const byTurn = new Map<string, DecisionRecord[]>();
  for (const r of records) byTurn.set(r.turn_id, [...(byTurn.get(r.turn_id) ?? []), r]);
  const firstSeen = new Map<string, string>();
  for (const r of records) if (!firstSeen.has(r.turn_id) || r.ts < firstSeen.get(r.turn_id)!) firstSeen.set(r.turn_id, r.ts);
  const customerOf = (turn: string) => messages.find((m) => m.role === "customer" && m.turn_id === turn);
  return [...byTurn.entries()]
    .sort((a, b) => (firstSeen.get(b[0]) ?? "").localeCompare(firstSeen.get(a[0]) ?? "") || b[0].localeCompare(a[0]))
    .map(([turn, recs]) => buildTurn(recs, customerOf(turn)));
}
