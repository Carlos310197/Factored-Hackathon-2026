"use client";
import { useRef } from "react";
import type { HandoffRow } from "@/lib/contract";
import { fmtAge } from "@/lib/format";
import { PRIORITY_WORD, reasonText } from "@/lib/staff/actions";

export type QueueFilter = "open" | "mine" | "in_takeover" | "resolved";
const FILTERS: [QueueFilter, string][] = [["open", "Open"], ["mine", "Mine"], ["in_takeover", "In takeover"], ["resolved", "Resolved"]];
const MARK = { critical: "bg-c-alert", high: "bg-c-warn", medium: "bg-c-below" } as const;

export function Queue({ rows, filter, onFilter, selected, onSelect, fresh, me }: { rows: HandoffRow[]; filter: QueueFilter;
  onFilter: (f: QueueFilter) => void; selected?: string; onSelect: (id: string) => void; fresh: Set<string>; me: string }) {
  const list = useRef<HTMLUListElement>(null);
  const label = FILTERS.find(([f]) => f === filter)?.[1];
  const move = (id: string) => {
    onSelect(id);
    requestAnimationFrame(() => list.current?.querySelector<HTMLElement>('[aria-selected="true"]')?.focus());
  };
  return (
    <aside className="bg-c-panel border-r border-c-line flex flex-col min-h-0" aria-label="Case queue">
      <div className="flex items-baseline justify-between px-4 pt-3.5 pb-2">
        <h2 className="text-[11px] font-bold uppercase tracking-wider text-c-muted">Queue</h2>
        <span className="text-xs text-c-muted tabular-nums">{rows.length} {rows.length === 1 ? "case" : "cases"}</span>
      </div>
      <div role="tablist" aria-label="Queue filter" className="flex flex-wrap gap-1 px-3 pb-3 border-b border-c-line">
        {FILTERS.map(([f, name]) => (
          <button key={f} role="tab" aria-selected={filter === f} onClick={() => onFilter(f)}
            className={`rounded-control px-2.5 py-1 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-c-signal ${
              filter === f ? "bg-c-ink text-c-panel" : "bg-c-track text-c-ink hover:bg-c-line"}`}>{name}</button>
        ))}
      </div>
      {rows.length === 0 ? (
        <p className="p-4 text-sm text-c-muted">{filter === "open" ? "No open cases" : `Nothing in ${label}`}</p>
      ) : (
        <ul ref={list} role="listbox" aria-label="Cases" className="overflow-y-auto flex-1"
          onKeyDown={(e) => {
            const i = rows.findIndex((r) => r.handoff_id === selected);
            if (e.key === "ArrowDown" && i < rows.length - 1) { e.preventDefault(); move(rows[i + 1].handoff_id); }
            if (e.key === "ArrowUp" && i > 0) { e.preventDefault(); move(rows[i - 1].handoff_id); }
          }}>
          {rows.map((r, i) => {
            const on = selected === r.handoff_id;
            return (
              <li key={r.handoff_id} role="option" aria-selected={on}
                tabIndex={on || (!selected && i === 0) ? 0 : -1}
                onClick={() => onSelect(r.handoff_id)} onKeyDown={(e) => e.key === "Enter" && onSelect(r.handoff_id)}
                className={`grid grid-cols-[10px_1fr_auto] gap-x-2.5 gap-y-1 px-4 py-3 border-b border-c-track cursor-pointer outline-none
                  focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-c-signal
                  ${on ? "bg-c-signal-tint shadow-[inset_3px_0_0_var(--color-c-signal)]" : "hover:bg-c-canvas"}
                  ${fresh.has(r.handoff_id) ? "motion-safe:animate-[pulse_1s_ease-out_2] bg-c-signal-tint" : ""}`}>
                <span className={`mt-1 size-2.5 rounded-[3px] ${MARK[r.priority]}`} aria-hidden />
                <span className="font-bold text-sm">{r.handoff_id}</span>
                <span className="text-xs text-c-muted tabular-nums">{fmtAge(r.created_at)}</span>
                <span className="col-start-2 col-span-2 text-xs text-c-muted leading-snug">
                  {[PRIORITY_WORD[r.priority], ...r.reason_codes.slice(0, 2).map(reasonText), r.language.toUpperCase(),
                    r.claimed_by ? (r.claimed_by === me ? "held by you" : `held by ${r.claimed_by}`) : null].filter(Boolean).join(" · ")}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
