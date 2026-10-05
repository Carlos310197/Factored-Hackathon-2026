"use client";
import { redirectToStaffLogin } from "@/lib/staff/redirect";
import { useCallback, useEffect, useRef, useState } from "react";
import { HandoffPacket, HandoffRow, QueueEvent, type ResolutionCode } from "@/lib/contract";
import { useChannel } from "@/lib/realtime/useChannel";
import type { CaseAction } from "@/lib/staff/actions";
import { CaseHeader } from "./CaseHeader";
import { StaffSignOut } from "./StaffSignOut";
import { Queue, type QueueFilter } from "./Queue";

export type CaseData = { packet: HandoffPacket; control: string };
export type Tab = "packet" | "conversation" | "trace";
const FRESH_MS = 4000;
type CaseState = "missing" | "error" | null;

export function Console({ me, initialId, renderTab }: { me: { sub: string; name: string }; initialId?: string;
  renderTab?: (tab: Tab, c: CaseData) => React.ReactNode }) {
  const [filter, setFilter] = useState<QueueFilter>("open");
  const [rows, setRows] = useState<HandoffRow[]>([]);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<string | undefined>(initialId);
  const [data, setData] = useState<CaseData | null>(null);
  const [tab, setTab] = useState<Tab>("packet");
  const [notice, setNotice] = useState<string | null>(null);
  const [caseState, setCaseState] = useState<CaseState>(null);
  const rowsSeq = useRef(0);
  const caseSeq = useRef(0);
  const dataRef = useRef<CaseData | null>(null);
  useEffect(() => { dataRef.current = data; });
  const busy = useRef(false);
  const selectedRef = useRef(selected);
  useEffect(() => { selectedRef.current = selected; });
  const seen = useRef<Set<string>>(new Set()); // ids already shown, so only truly new rows get the highlight
  const timers = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());
  useEffect(() => { const t = timers.current; return () => t.forEach(clearTimeout); }, []);

  const loadRows = useCallback(async () => {
    const seq = ++rowsSeq.current; // a slow response for an old filter must not overwrite the current one
    try {
      const r = await fetch(`/api/handoffs?filter=${filter}`, { cache: "no-store" });
      if (r.status === 401) return redirectToStaffLogin();
      if (r.ok && seq === rowsSeq.current) {
        const list = HandoffRow.array().parse((await r.json()).data);
        list.forEach((x) => seen.current.add(x.handoff_id));
        setRows(list);
      }
    } catch { /* the next poll or push retries */ }
  }, [filter]);
  const loadCase = useCallback(async (id: string) => {
    const seq = ++caseSeq.current; // a stale response must not show case A while B is selected
    try {
      const r = await fetch(`/api/handoffs/${id}`, { cache: "no-store" });
      if (seq !== caseSeq.current) return;
      if (r.status === 401) return redirectToStaffLogin();
      if (!r.ok) { setData(null); return setCaseState(r.status === 404 ? "missing" : "error"); }
      const d = (await r.json()).data;
      const packet = HandoffPacket.parse(d.packet);
      if (seq !== caseSeq.current) return;
      setData({ packet, control: String(d.control) });
      setCaseState(null);
    } catch { if (seq === caseSeq.current) setCaseState((s) => (dataRef.current ? s : "error")); }
  }, []);
  // Load-then-listen: these effects only start fetches; state is set after the response arrives.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadRows(); }, [loadRows]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (selected) void loadCase(selected); }, [selected, loadCase]);
  useChannel("/queue/all", (payload) => {
    const ev = QueueEvent.safeParse(payload);
    if (!ev.success) return;
    const id = ev.data.handoff_id;
    if (ev.data.status === "open" && !seen.current.has(id)) {
      setFresh((s) => new Set(s).add(id));
      const t = setTimeout(() => { timers.current.delete(t); setFresh((s) => { const n = new Set(s); n.delete(id); return n; }); }, FRESH_MS);
      timers.current.add(t);
    }
    seen.current.add(id);
    void loadRows();
    if (id === selected) void loadCase(id);
  }, { as: "staff", onResync: () => { void loadRows(); if (selected) void loadCase(selected); } });

  async function act(a: CaseAction, body?: { code: ResolutionCode; note: string }) {
    if (!data || busy.current) return;
    const id = data.packet.handoff_id; // the case on screen, not whatever is selected now
    busy.current = true;
    try {
      const r = await fetch(`/api/handoffs/${id}/${a}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body ?? {}) });
      setNotice(r.status === 409 ? "Someone else changed this case. It has been refreshed."
        : r.status === 404 ? "This case no longer exists."
        : r.ok ? null : "That didn't work. Try again.");
      if (a === "takeover" && r.ok) setTab("conversation");
    } catch { setNotice("That didn't work. Try again."); }
    finally { busy.current = false; }
    // the user may have moved to another case meanwhile; reloading A would cancel B's load
    await Promise.all([selectedRef.current === id ? loadCase(id) : null, loadRows()]);
  }

  return (
    <div className="font-staff h-dvh flex flex-col bg-c-canvas text-c-ink">
      <div className="flex justify-between items-center px-5 py-2.5 bg-c-ink text-c-canvas text-sm">
        <b>LATAM Bank · Agent console</b><span className="flex items-center gap-3"><span className="text-xs opacity-80">{me.name} · test identity</span><StaffSignOut /></span>
      </div>
      <div className="grid grid-cols-[290px_1fr] flex-1 min-h-0">
        <Queue rows={rows} filter={filter} onFilter={setFilter} selected={selected} onSelect={(id) => { if (id === selected) return; caseSeq.current++; setData(null); setCaseState(null); setSelected(id); setTab("packet"); setNotice(null); }} fresh={fresh} me={me.sub} />
        <section className="p-5 overflow-y-auto min-w-0">
          {notice && <p role="status" className="mb-2 text-sm text-c-alert">{notice}</p>}
          {!data ? (
            caseState === "missing" ? <p role="alert" className="text-sm text-c-alert">This case no longer exists.</p>
            : caseState === "error" ? <p role="alert" className="text-sm text-c-alert">Couldn&apos;t load this case. Pick it again to retry.</p>
            : <p className="text-sm text-c-muted">{selected ? "Loading case…" : "Select a case from the queue."}</p>
          ) : (
            <>
              <CaseHeader packet={data.packet} control={data.control} me={me} onAction={(a, b) => void act(a, b)} />
              <div role="tablist" className="flex gap-0.5 mt-4 mb-3 border-b border-c-line">
                {(["packet", "conversation", "trace"] as const).map((k) => (
                  <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                    className={`px-3.5 py-2 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-c-signal ${tab === k ? "text-c-ink shadow-[inset_0_-2px_0_var(--color-c-signal)]" : "text-c-muted hover:text-c-ink"}`}>
                    {k[0].toUpperCase() + k.slice(1)}
                  </button>
                ))}
              </div>
              <div role="tabpanel">{renderTab ? renderTab(tab, data) : <p className="text-sm text-c-muted">Loading…</p>}</div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
