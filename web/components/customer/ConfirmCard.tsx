"use client";
import { useId } from "react";
import type { Lang, Summary } from "@/lib/contract";
import { fmtDate, fmtMoney } from "@/lib/format";
import { t } from "@/lib/i18n";

export function ConfirmCard({ summary, lang, disabled, onConfirm, onChange }:
  { summary: Summary; lang: Lang; disabled: boolean; onConfirm: () => void; onChange: () => void }) {
  const d = t(lang);
  const titleId = useId();
  const reason = summary.reason_code ? (d.reasons as Record<string, string>)[summary.reason_code] ?? summary.reason_code : null;
  const rows: [string, string | null][] = [
    [d.merchant, summary.merchant || null],
    [d.date, summary.date ? fmtDate(summary.date, lang) : null],
    [d.amount, summary.amount != null && summary.currency ? fmtMoney(summary.amount, summary.currency, lang) : null],
    [d.reason, reason],
  ];
  return (
    <section aria-labelledby={titleId} className="max-w-[92%] self-start overflow-hidden rounded-card border border-b-sun bg-b-sun-tint motion-safe:animate-[fade-in_220ms_ease-out]">
      <h2 id={titleId} className="flex items-center gap-2 px-4 pt-3 text-base font-extrabold">
        <span aria-hidden className="size-2.5 rounded-full bg-b-sun" />{d.confirmTitle}
      </h2>
      <dl className="px-4 pb-1 pt-2 text-sm">
        {rows.filter((r): r is [string, string] => r[1] !== null).map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 border-b border-b-sun/40 py-1.5 last:border-0">
            <dt className="text-b-muted">{k}</dt><dd className="text-right font-semibold tabular-nums">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-2 px-4 pb-4 pt-2">
        <button type="button" disabled={disabled} onClick={onConfirm}
          className="min-h-11 rounded-full bg-b-leaf px-4 text-sm font-bold text-b-surface transition-transform duration-150 hover:opacity-90 active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-cobalt disabled:opacity-60">{d.confirm}</button>
        <button type="button" disabled={disabled} onClick={onChange}
          className="min-h-11 rounded-full border-[1.5px] border-b-ink bg-b-surface px-4 text-sm font-bold text-b-ink transition-transform duration-150 active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-cobalt disabled:opacity-60">{d.change}</button>
      </div>
    </section>
  );
}
