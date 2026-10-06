"use client";
import { useCallback, useEffect, useState } from "react";
import { HandoffPacket, HandoffRow } from "@/lib/contract";
import { fmtAge } from "@/lib/format";
import { useChannel } from "@/lib/realtime/useChannel";
import type { TraceTurn } from "@/lib/trace/viewModel";
import { ConsoleWithTabs } from "../staff/ConsoleWithTabs";

type Me = { sub: string; name: string };
const FILTERS = [["open", "Open"], ["mine", "Mine"], ["in_takeover", "In takeover"], ["resolved", "Resolved"]] as const;
type Lists = Record<(typeof FILTERS)[number][0], HandoffRow[]>;
const EMPTY: Lists = { open: [], mine: [], in_takeover: [], resolved: [] };
// Evidence-tagged figures from reports/asis-2026-10-05.md §4 (8,199 dispute complaints, 2025-06-17 → 2026-06-17).
const ASIS = { firstResponse: "37.0 h", resolution: "15.5 d", stillOpen: "69.8 %" };

const secs = (ms: number) => `${(ms / 1000).toFixed(1)} s`;

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 py-0.5">
      <dt className="text-c-muted">{label}</dt>
      <dd className="font-bold tabular-nums text-right">{value}{hint && <small className="block font-normal text-c-muted text-[11px]">{hint}</small>}</dd>
    </div>
  );
}

function Card({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="bg-c-panel rounded-[var(--radius-panel)] ring-1 ring-c-line p-3 text-sm min-w-0">
      <h3 className="text-[11px] font-bold uppercase tracking-wider text-c-muted mb-1.5">{title}</h3>
      <dl>{children}</dl>
      {note && <p className="text-[11px] text-c-muted mt-1">{note}</p>}
    </section>
  );
}

/** Demo act 4: the human-agent side of the phone's conversation, with live and as-is numbers above the case. */
export function HandoffPanel({ sid, me, refreshKey }: { sid: string | null; me: Me; refreshKey: number }) {
  const [lists, setLists] = useState<Lists>(EMPTY);
  // tagged with what they were fetched for, so a stale case or session never shows (no reset needed)
  const [got, setPacket] = useState<HandoffPacket | null>(null);
  const [trace, setTrace] = useState<{ sid: string; turns: TraceTurn[] } | null>(null);

  const loadLists = useCallback(async () => {
    const got = await Promise.all(FILTERS.map(async ([f]) => {
      try {
        const r = await fetch(`/api/handoffs?filter=${f}`, { cache: "no-store" });
        return r.ok ? HandoffRow.array().parse((await r.json()).data) : [];
      } catch { return []; } // the next push or poll retries
    }));
    setLists(Object.fromEntries(FILTERS.map(([f], i) => [f, got[i]])) as Lists);
  }, []);
  useChannel("/queue/all", () => { void loadLists(); }, { as: "staff", onResync: () => { void loadLists(); }, pollMs: 15_000 });
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadLists(); }, [loadLists, refreshKey]);

  const mine = sid ? Object.values(lists).flat().filter((r) => r.session_id === sid) : [];
  const handoff = mine.sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  const id = handoff?.handoff_id;
  const status = handoff?.status;

  useEffect(() => {
    if (!id) return;
    let live = true;
    fetch(`/api/handoffs/${encodeURIComponent(id)}`, { cache: "no-store" })
      .then(async (r) => { if (r.ok && live) setPacket(HandoffPacket.parse((await r.json()).data.packet)); })
      .catch(() => {});
    return () => { live = false; };
  }, [id, status]);

  useEffect(() => {
    if (!sid) return;
    let live = true;
    fetch(`/api/trace/${encodeURIComponent(sid)}`, { cache: "no-store" })
      .then(async (r) => { if (r.ok && live) setTrace({ sid, turns: (await r.json()).data }); })
      .catch(() => {});
    return () => { live = false; };
  }, [sid, refreshKey]);

  if (!sid) return <p className="text-sm text-c-muted">Sign in on the phone to start a session.</p>;

  const packet = got?.handoff_id === id ? got : null;
  const turns = trace?.sid === sid ? trace.turns : [];
  const timed = turns.filter((t) => t.durationMs != null).map((t) => t.durationMs!);
  const claimed = packet?.claimed_at ? (Date.parse(packet.claimed_at) - Date.parse(packet.created_at)) / 1000 : null;
  const oldest = lists.open.map((r) => r.created_at).sort()[0];

  return (
    <div className="min-w-0">
      <div className="grid grid-cols-3 gap-3 mb-4">
        <Card title="This conversation">
          <Stat label="Turns" value={String(turns.length)} />
          <Stat label="Mean reply" value={timed.length ? secs(timed.reduce((a, b) => a + b, 0) / timed.length) : "—"} />
          <Stat label="Template fallbacks" value={String(turns.filter((t) => t.replyCheck?.template).length)} />
          <Stat label="Handoff → claimed" value={claimed != null ? `${Math.round(claimed)} s` : handoff ? `waiting ${fmtAge(handoff.created_at)}` : "—"} />
        </Card>
        <Card title="Queue now">
          {FILTERS.map(([f, label]) => <Stat key={f} label={label} value={String(lists[f].length)} />)}
          <Stat label="Oldest open" value={oldest ? fmtAge(oldest) : "—"} />
        </Card>
        <Card title="Disputes today vs here" note="Medians, 8,199 dispute complaints, Jun 2025–Jun 2026">
          <Stat label="First response" value={ASIS.firstResponse} hint={timed.length ? `here: ${secs(timed[0])}` : undefined} />
          <Stat label="Time to resolve" value={ASIS.resolution} />
          <Stat label="Still open" value={ASIS.stillOpen} />
        </Card>
      </div>
      {id ? <ConsoleWithTabs key={id} me={me} initialId={id} caseOnly />
        : <p className="text-sm text-c-muted">No handoff yet for this conversation. Run a scenario that needs a person, e.g. “Unauthorized → handoff”.</p>}
    </div>
  );
}
