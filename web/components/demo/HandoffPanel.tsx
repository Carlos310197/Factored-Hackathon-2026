"use client";
import { useCallback, useEffect, useState } from "react";
import { HandoffRow } from "@/lib/contract";
import { useChannel } from "@/lib/realtime/useChannel";
import { ConsoleWithTabs } from "../staff/ConsoleWithTabs";
import { FILTERS } from "../staff/Queue";

type Me = { sub: string; name: string };

/** Demo act 4: the human-agent side of the phone's conversation. The case's own numbers live in the console (CaseStats). */
export function HandoffPanel({ sid, me, refreshKey }: { sid: string | null; me: Me; refreshKey: number }) {
  const [rows, setRows] = useState<HandoffRow[]>([]);
  const load = useCallback(async () => {
    const got = await Promise.all(FILTERS.map(async ([f]) => {
      try {
        const r = await fetch(`/api/handoffs?filter=${f}`, { cache: "no-store" });
        return r.ok ? HandoffRow.array().parse((await r.json()).data) : [];
      } catch { return []; } // the next push or poll retries
    }));
    setRows(got.flat());
  }, []);
  useChannel("/queue/all", () => { void load(); }, { as: "staff", onResync: () => { void load(); }, pollMs: 15_000 });
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load, refreshKey]);

  if (!sid) return <p className="text-sm text-c-muted">Sign in on the phone to start a session.</p>;
  const id = rows.filter((r) => r.session_id === sid).sort((a, b) => b.created_at.localeCompare(a.created_at))[0]?.handoff_id;

  return (
    <div className="min-w-0">
      {/* Evidence-tagged medians from reports/asis-2026-10-05.md §4 (8,199 dispute complaints, 2025-06-17 → 2026-06-17). */}
      <p className="mb-3 text-sm text-c-muted"><b className="text-c-ink">Disputes today:</b> first response 37.0 h · resolved in 15.5 d · 69.8 % still open
        <span className="text-xs"> (medians, 8,199 complaints, Jun 2025–Jun 2026)</span></p>
      {id ? <ConsoleWithTabs key={id} me={me} initialId={id} caseOnly />
        : <p className="text-sm text-c-muted">No handoff yet for this conversation. Run a scenario that needs a person, e.g. “Unauthorized → handoff”.</p>}
    </div>
  );
}
