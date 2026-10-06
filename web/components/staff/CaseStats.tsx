"use client";
import { useEffect, useState } from "react";
import type { HandoffPacket } from "@/lib/contract";
import { fmtAge } from "@/lib/format";
import type { TraceTurn } from "@/lib/trace/viewModel";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** One line of numbers about the conversation behind a case: how the assistant did, and how fast a person picked it up. */
export function CaseStats({ packet }: { packet: HandoffPacket }) {
  const sid = packet.session_id;
  // tagged with the session it was fetched for, so the previous case's numbers never show
  const [trace, setTrace] = useState<{ sid: string; turns: TraceTurn[] } | null>(null);
  useEffect(() => {
    let live = true;
    fetch(`/api/trace/${encodeURIComponent(sid)}`, { cache: "no-store" })
      .then(async (r) => { const d = r.ok ? (await r.json()).data : null; if (live && Array.isArray(d)) setTrace({ sid, turns: d }); })
      .catch(() => {}); // no trace: the turn numbers stay out
    return () => { live = false; };
  }, [sid, packet.status]);

  const turns = trace?.sid === sid ? trace.turns : null;
  const timed = (turns ?? []).flatMap((t) => (t.durationMs != null ? [t.durationMs] : []));
  const claimS = packet.claimed_at ? Math.round((Date.parse(packet.claimed_at) - Date.parse(packet.created_at)) / 1000) : null;
  const items = [
    turns && plural(turns.length, "turn"),
    timed.length > 0 && `mean reply ${(timed.reduce((a, b) => a + b, 0) / timed.length / 1000).toFixed(1)} s`,
    turns && plural(turns.filter((t) => t.replyCheck?.template).length, "template fallback"),
    claimS != null ? `claimed ${claimS < 120 ? `${claimS} s` : `${Math.round(claimS / 60)} min`} after handoff` : `waiting ${fmtAge(packet.created_at)}`,
  ].filter(Boolean) as string[];

  return (
    <ul aria-label="Conversation stats" className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs text-c-muted tabular-nums">
      {items.map((t, i) => <li key={t} className={i ? "before:content-['·'] before:mr-3" : ""}>{t}</li>)}
    </ul>
  );
}
