"use client";
import { useState } from "react";
import { QueueEvent } from "@/lib/contract";
import { useChannel } from "@/lib/realtime/useChannel";

export function HandoffTicker() {
  const [last, setLast] = useState<{ id: string; priority: string } | null>(null);
  useChannel("/queue/all", (p) => {
    const ev = QueueEvent.safeParse(p);
    if (ev.success && ev.data.status === "open") setLast({ id: ev.data.handoff_id, priority: ev.data.priority });
  }, { as: "staff", onResync: () => undefined, pollMs: 60_000 });
  return (
    <section className="mt-3 border-t border-c-track pt-3 text-sm" aria-live="polite">
      <h2 className="font-bold mb-2">Handoffs</h2>
      {last ? (
        <>
          <p className="rounded-[var(--radius-control)] bg-c-alert-tint text-c-alert px-2.5 py-2 font-bold">{`${last.id} arrived · ${last.priority}`}</p>
          <a className="block mt-1.5 text-c-signal font-bold" href={`/agent/${last.id}`} target="_blank" rel="noreferrer">Open in console ↗</a>
        </>
      ) : <p className="text-c-muted">None yet in this demo.</p>}
    </section>
  );
}
