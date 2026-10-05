"use client";
import { useState } from "react";
import type { TraceBar, TraceTurn } from "@/lib/trace/viewModel";
import { Gauge } from "./Gauge";

function BarRow({ bar, reveal, index }: { bar: TraceBar; reveal: boolean; index: number }) {
  return (
    <div className="bg-c-panel rounded-[var(--radius-panel)] ring-1 ring-c-line px-3.5 pt-2.5 pb-2 mb-2">
      <div className="flex justify-between items-baseline gap-2 text-sm">
        <span className="font-bold">{bar.label}</span>
        <span className="text-[13px] font-semibold whitespace-nowrap">{`${bar.verdict.icon} ${bar.verdict.text}`}</span>
      </div>
      <div className="grid grid-cols-[1fr_40px] gap-2 items-center mt-2.5">
        <Gauge bar={bar} reveal={reveal} index={index} />
        <span className="text-xs font-bold tabular-nums text-right">{bar.value.toFixed(2)}</span>
      </div>
      <p className="text-[11px] text-c-muted mt-1 tabular-nums">
        {bar.threshold !== null ? `threshold ${bar.threshold.toFixed(2)}` : "no threshold (used on this path)"}{bar.detail ? ` · ${bar.detail}` : ""}
      </p>
      {bar.candidates?.length ? (
        <p className="text-[11px] text-c-muted">resolver top-3: {bar.candidates.map((c) => `${c.alias} ${c.label} ${c.score.toFixed(2)}${c.why.length ? ` (${c.why.join(", ")})` : ""}`).join(" · ")}</p>
      ) : null}
    </div>
  );
}

export function TraceTurnView({ turn, reveal = false, collapsed = false, onToggle }:
  { turn: TraceTurn; reveal?: boolean; collapsed?: boolean; onToggle?: () => void }) {
  const [open, setOpen] = useState(false);
  const [checkOpen, setCheckOpen] = useState(false);
  const failed = turn.route.policy.filter((p) => !p.passed);
  const policy = [...failed, ...turn.route.policy.filter((p) => p.passed)].slice(0, 3)
    .map((p) => `${p.name.replaceAll("_", " ")} ${p.passed ? "✓" : "✗"}`).join(" · ");
  const versions = [turn.versions.questionSet, turn.versions.thresholds].filter(Boolean).join(" · ");
  const strip = (
    <div title={versions || undefined}
      className="flex justify-between gap-3 rounded-[var(--radius-control)] bg-c-ink text-c-canvas px-3 py-2 text-[13px]">
      <span>{policy ? `Policy: ${policy}` : turn.errors.length ? "Nothing crossed; see errors above" : "Nothing crossed"}</span>
      <b>{`Route: ${turn.route.next}${turn.route.priority ? ` · ${turn.route.priority}` : ""}`}</b>
    </div>
  );
  return (
    <article className={`rounded-[var(--radius-panel)] p-2.5 mb-2.5 ${reveal ? "bg-c-panel ring-2 ring-c-signal" : "bg-c-canvas"}`}>
      <header className="flex justify-between gap-2 text-[11px] text-c-muted mb-1.5">
        <button type="button" onClick={onToggle} disabled={!onToggle} aria-expanded={onToggle ? !collapsed : undefined} className="text-left">
          <span>“{turn.quote || "(no customer text)"}”</span>{turn.quoteEn ? <span className="block">EN: {turn.quoteEn}</span> : null}
        </button>
        {turn.durationMs !== null && <span className="tabular-nums whitespace-nowrap">{(turn.durationMs / 1000).toFixed(1)} s</span>}
      </header>
      {!collapsed && (
        <>
          {turn.bars.map((b, i) => <BarRow key={b.signal} bar={b} reveal={reveal} index={i} />)}
          {turn.folded.count > 0 && (
            <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}
              className="w-full text-left text-xs text-c-muted border border-dashed border-c-line rounded-[var(--radius-panel)] px-3.5 py-2 mb-2">
              {`${open ? "▾" : "▸"} ${turn.folded.count} more signals below threshold${turn.folded.highest ? ` · highest ${turn.folded.highest.label} ${turn.folded.highest.value.toFixed(2)}` : ""}`}
            </button>
          )}
          {open && turn.folded.bars.map((b, i) => <BarRow key={b.signal} bar={b} reveal={false} index={i} />)}
          {turn.replyCheck && (turn.replyCheck.failed || turn.replyCheck.template || turn.replyCheck.regenerated > 0 ? (
            <button type="button" aria-expanded={checkOpen} onClick={() => setCheckOpen((o) => !o)}
              className={`w-full text-left text-xs mb-2 px-1 text-c-alert ${checkOpen ? "" : "truncate"}`}>
              {`${checkOpen ? "▾" : "▸"} ${turn.replyCheck.text}`}
            </button>
          ) : <p className="text-xs mb-2 px-1 text-c-muted">{turn.replyCheck.text}</p>)}
          {turn.errors.map((e) => <p key={e} className="text-xs mb-1.5 px-1 text-c-alert">{e}</p>)}
        </>
      )}
      {strip}
    </article>
  );
}
