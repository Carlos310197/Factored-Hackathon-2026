"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { TraceEvent } from "@/lib/contract";
import { useChannel } from "@/lib/realtime/useChannel";
import { stageOf, type Stage } from "@/lib/trace/stages";
import type { TraceTurn } from "@/lib/trace/viewModel";
import { AnalysingCard } from "./AnalysingCard";
import { TraceTurnView } from "./TraceTurn";

export function TraceList({ sid, mode, refreshKey = 0, running = false, onTurnComplete }:
  { sid: string; mode: "page" | "console" | "demo"; refreshKey?: number; running?: boolean; onTurnComplete?: (turnId: string) => void }) {
  const [turns, setTurns] = useState<TraceTurn[]>([]);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [live, setLive] = useState<{ turnId: string; lit: Stage[]; current: Stage | null } | null>(null);
  const [announce, setAnnounce] = useState("");
  const current = useRef(sid);
  useEffect(() => { current.current = sid; });

  const load = useCallback(async (reveal: boolean) => {
    try {
      const r = await fetch(`/api/trace/${encodeURIComponent(sid)}`, { cache: "no-store" });
      if (!r.ok || current.current !== sid) return; // stale: another case is open now
      const data = (await r.json()).data as TraceTurn[];
      setTurns(data);
      if (reveal && data[0]) { setRevealed(data[0].turnId); setAnnounce(`Turn ${data.length}: route ${data[0].route.next}`); }
    } catch { /* keep what is shown; the next event or resync retries */ }
  }, [sid]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { setTurns([]); setRevealed(null); setLive(null); void load(false); }, [load]); // reset per sid
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (refreshKey > 0) { setLive(null); void load(true); } }, [refreshKey, load]);
  useChannel(`/trace/${sid}`, (p) => {
    const ev = TraceEvent.safeParse(p);
    if (!ev.success) return;
    if (ev.data.type === "record") {
      const stage = stageOf(ev.data.node, ev.data.kind);
      const turnId = ev.data.turn_id;
      if (!stage) return;
      setLive((l) => {
        const base = l && l.turnId === turnId ? l : { turnId, lit: [] as Stage[], current: null };
        const lit = base.current && base.current !== stage && !base.lit.includes(base.current) ? [...base.lit, base.current] : base.lit;
        return { turnId, lit, current: stage };
      });
    } else {
      setLive(null);
      onTurnComplete?.(ev.data.turn_id);
      void load(true);
    }
  }, { as: "staff", onResync: () => void load(false) });

  const showAnalysing = live !== null || running;
  return (
    <div>
      <p className="sr-only" aria-live="polite">{announce}</p>
      {showAnalysing && <AnalysingCard turnNumber={turns.length + 1} lit={live?.lit ?? []} current={live?.current ?? null} />}
      {turns.length === 0 && !showAnalysing && <p className="text-sm text-c-muted">No turns yet: send a message to see the first decision.</p>}
      {turns.map((t, i) => {
        const collapsed = mode === "demo" ? i > 0 && !expanded.has(t.turnId) : false;
        return <TraceTurnView key={t.turnId} turn={t} reveal={t.turnId === revealed} collapsed={collapsed}
          onToggle={mode === "demo" ? () => setExpanded((s) => { const n = new Set(s); if (n.has(t.turnId)) n.delete(t.turnId); else n.add(t.turnId); return n; }) : undefined} />;
      })}
    </div>
  );
}
