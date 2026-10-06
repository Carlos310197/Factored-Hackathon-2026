"use client";
import { useEffect, useId, useRef, useState } from "react";
import type { CustomerCase, Lang } from "@/lib/contract";
import { fmtDate, fmtMoney } from "@/lib/format";
import { t } from "@/lib/i18n";

const PILL: Record<string, string> = {
  submitted: "bg-b-mist text-b-cobalt", pending_review: "bg-b-sun-tint text-b-ink",
  resolved: "bg-b-receipt text-b-receipt-ink", rejected: "bg-b-fog text-b-muted",
};
/** DSP-<13 digit ms><8 hex>: the prefix plus the random tail is enough to tell cases apart on a phone. */
const shortId = (id: string) => (id.length > 16 ? `${id.slice(0, 4)}…${id.slice(-8)}` : id);

/** "Mis casos": a header button opening a sheet with the customer's disputes, fetched on each open. */
export function CasesPanel({ lang }: { lang: Lang }) {
  const d = t(lang);
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [cases, setCases] = useState<CustomerCase[] | null>(null);
  const [failed, setFailed] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const closer = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closer.current?.focus();
    const ctl = new AbortController();
    fetch("/api/customer/cases", { signal: ctl.signal, cache: "no-store" })
      .then(async (r) => { if (!r.ok) throw new Error(String(r.status)); setCases((await r.json()).data); })
      .catch(() => { if (!ctl.signal.aborted) setFailed(true); });
    return () => ctl.abort();
  }, [open]);

  const close = () => { setOpen(false); opener.current?.focus(); };
  const btn = "min-h-11 rounded-full px-4 text-sm font-bold focus-visible:outline-2 focus-visible:outline-offset-2";

  return (
    <>
      <button ref={opener} type="button" aria-haspopup="dialog" onClick={() => { setCases(null); setFailed(false); setOpen(true); }}
        className={`${btn} bg-b-surface/15 text-b-surface focus-visible:outline-b-surface`}>{d.myCases}</button>
      {open && (
        <div className="fixed inset-0 z-10 flex items-end justify-center bg-b-ink/40 text-b-ink" onClick={(e) => { if (e.target === e.currentTarget) close(); }}>
          {/* ponytail: the close button is the only focusable element, so Tab just stays on it (no general focus trap) */}
          <div role="dialog" aria-modal="true" aria-labelledby={titleId}
            onKeyDown={(e) => { if (e.key === "Escape") close(); if (e.key === "Tab") { e.preventDefault(); closer.current?.focus(); } }}
            className="flex max-h-[80dvh] w-full max-w-md flex-col gap-3 rounded-t-card bg-b-surface p-6 pb-8 motion-safe:animate-[fade-in_220ms_ease-out]">
            <span aria-hidden className="mx-auto h-1 w-10 rounded-full bg-b-line" />
            <div className="flex items-center justify-between gap-3">
              <h2 id={titleId} className="text-xl font-extrabold">{d.myCases}</h2>
              <button ref={closer} type="button" onClick={close} className={`${btn} bg-b-fog text-b-cobalt focus-visible:outline-b-cobalt`}>{d.close}</button>
            </div>
            <div aria-live="polite" className="min-h-0 overflow-y-auto">
              {failed ? <p role="alert" className="text-sm text-b-muted">{d.casesFailed}</p>
                : !cases ? <p className="text-sm text-b-muted">{d.loading}</p>
                : !cases.length ? <p className="text-sm text-b-muted">{d.noCases}</p>
                : (
                  <ul className="flex flex-col gap-2">
                    {cases.map((c) => (
                      <li key={c.dispute_id} className="flex items-start justify-between gap-3 rounded-card border border-b-line px-4 py-3">
                        <div className="flex min-w-0 flex-col gap-0.5 text-sm">
                          <span className="font-bold">{(d.reasons as Record<string, string>)[c.reason] ?? c.reason}</span>
                          {c.amount != null && c.currency && <span className="tabular-nums">{fmtMoney(c.amount, c.currency, lang)}</span>}
                          <span className="text-xs text-b-muted tabular-nums"><span title={c.dispute_id}>{shortId(c.dispute_id)}</span> · {fmtDate(c.created_at, lang)}</span>
                        </div>
                        <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ${PILL[c.status] ?? PILL.rejected}`}>{d.caseStatus[c.status] ?? c.status}</span>
                      </li>
                    ))}
                  </ul>
                )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
