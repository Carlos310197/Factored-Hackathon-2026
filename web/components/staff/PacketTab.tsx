import type { HandoffPacket } from "@/lib/contract";
import type { TraceBar, TraceTurn } from "@/lib/trace/viewModel";
import { Gauge } from "../trace/Gauge";

/** The crossed bars of the turn that routed to handoff. */
export function whyBars(turns: TraceTurn[]): TraceBar[] {
  const t = turns.find((x) => x.route.next === "handoff");
  return t ? t.bars.filter((b) => b.crossed) : [];
}

const Box = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="bg-c-panel rounded-[var(--radius-panel)] ring-1 ring-c-line px-3 py-2.5 mb-3">
    <h2 className="text-[13px] font-bold mb-1.5">{title}</h2>{children}
  </section>
);
const words = (s: string) => s.replaceAll("_", " ");

export function PacketTab({ packet, why }: { packet: HandoffPacket; why: TraceBar[] }) {
  const checks = [...packet.policy_checks].sort((a, b) => Number(a.passed) - Number(b.passed)); // failed first
  return (
    <div className="grid grid-cols-[1.2fr_1fr] gap-3 text-[13px]">
      <div>
        <Box title="Customer request">
          <p>“{packet.customer_request.original}”</p>
          <p className="text-xs text-c-muted mt-1">EN: {packet.customer_request.en}</p>
        </Box>
        <Box title="Verified facts">
          {packet.verified_facts.length ? packet.verified_facts.map((f) => (
            <p key={f.receipt_id + f.fact} className="flex justify-between gap-2 py-1 border-b border-c-canvas last:border-0">
              <span>{f.fact}</span><span className="text-[11px] text-c-muted whitespace-nowrap">rcpt {f.receipt_id}</span></p>
          )) : <p className="text-c-muted">No verified facts in this packet.</p>}
        </Box>
        <Box title="Actions taken">
          {packet.actions_taken.length ? packet.actions_taken.map((a) => (
            <p key={a.receipt_id} className="flex justify-between gap-2 py-1"><span>{words(a.action)} · {words(a.result)}</span>
              <span className="text-[11px] text-c-muted whitespace-nowrap">rcpt {a.receipt_id}</span></p>
          )) : <p className="text-c-muted">No actions were taken.</p>}
        </Box>
      </div>
      <div>
        <Box title="Why it came to you">
          {why.length ? why.map((b) => (
            <div key={b.signal} className="grid grid-cols-[1fr_90px_36px] gap-1.5 items-center py-0.5 text-xs">
              <span>{b.label}</span><Gauge bar={b} compact /><span className="text-right font-bold">{b.value.toFixed(2)}</span>
            </div>
          )) : <p className="text-c-muted text-xs">The customer asked for a person, or the trace isn&apos;t available.</p>}
          <p className="text-[11px] text-c-muted mt-1">Full detail in the Trace tab</p>
        </Box>
        <Box title="Policy checks">
          {checks.length ? checks.map((c) => (
            <p key={c.rule} data-testid="policy-check" className="flex justify-between py-0.5">
              <span>{words(c.rule)} <span className="sr-only">{c.rule}</span></span>
              <b className={c.passed ? "text-c-pass" : "text-c-alert"}>{c.passed ? "pass" : "fail"}</b></p>
          )) : <p className="text-c-muted">None ran.</p>}
        </Box>
        <Box title="Open questions">
          {packet.open_questions.length ? packet.open_questions.map((q) => (
            <p key={q} className="py-0.5 pl-3 relative before:content-['?'] before:absolute before:left-0 before:text-c-signal before:font-bold">{q}</p>
          )) : <p className="text-c-muted">None.</p>}
        </Box>
      </div>
    </div>
  );
}
