import type { TraceBar } from "@/lib/trace/viewModel";

export function Gauge({ bar, compact = false, reveal = false, index = 0 }: { bar: TraceBar; compact?: boolean; reveal?: boolean; index?: number }) {
  const pct = Math.round(bar.value * 100);
  const th = bar.threshold !== null ? `, threshold ${bar.threshold.toFixed(2)}` : "";
  return (
    <div role="meter" aria-label={bar.label} aria-valuemin={0} aria-valuemax={1} aria-valuenow={bar.value}
      aria-valuetext={`${bar.value.toFixed(2)}${th}, ${bar.verdict.text}`}
      className={`relative rounded-[3px] bg-c-track ${compact ? "h-2" : "h-3"}`}>
      <div className={`absolute inset-y-0 left-0 rounded-[3px] ${reveal ? "motion-safe:animate-[grow_400ms_ease-out_both]" : ""}`}
        style={{ width: `${pct}%`, background: bar.color, animationDelay: reveal ? `${index * 60}ms` : undefined }} />
      {bar.threshold !== null && (
        <div className="absolute -top-1 -bottom-1 w-0.5 bg-c-ink" style={{ left: `${bar.threshold * 100}%` }} title={`threshold ${bar.threshold.toFixed(2)}`} />
      )}
    </div>
  );
}
