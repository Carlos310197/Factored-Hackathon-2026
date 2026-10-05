import { STAGES, type Stage } from "@/lib/trace/stages";

export function AnalysingCard({ turnNumber, lit, current }: { turnNumber: number; lit: Stage[]; current: Stage | null }) {
  return (
    <div className="bg-c-panel rounded-[var(--radius-panel)] ring-1 ring-c-line p-3.5 mb-2.5" aria-busy="true">
      <b>{`Analysing turn ${turnNumber}…`}</b>
      <div className="flex gap-1.5 my-2.5">
        {STAGES.map((s) => {
          const state = s.key === current ? "now" : lit.includes(s.key) ? "done" : "pending";
          return (
            <span key={s.key} data-state={state} className={`flex-1 text-center py-1.5 rounded-[var(--radius-control)] font-semibold text-xs
              ${state === "done" ? "bg-c-pass/10 text-c-pass" : state === "now" ? "bg-c-signal-tint text-c-signal ring-[1.5px] ring-c-signal" : "bg-c-canvas text-c-below"}`}>
              {s.label}
            </span>
          );
        })}
      </div>
      <p className="text-[11px] text-c-muted">The trace for this turn appears in full once the reply is sent.</p>
    </div>
  );
}
