"use client";
import { useCallback, useEffect, useState } from "react";
import { useStore } from "zustand";
import { syncHistory } from "@/lib/chat/api";
import { createChatStore } from "@/lib/chat/store";
import { SessionEvent, type Lang } from "@/lib/contract";
import { useChannel } from "@/lib/realtime/useChannel";
import { systemLine } from "../customer/MessageView";

const WHO = { customer: "Customer", assistant: "Assistant", agent: "Agent" } as const;
const WRITE_IN = { es: "Write in Spanish", pt: "Write in Portuguese" } as const;

export function ConversationTab({ sid, lang, control, me }: { sid: string; lang: Lang; control: string; me: { sub: string; name: string } }) {
  const [store] = useState(createChatStore);
  const messages = useStore(store, (s) => s.messages);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const holding = control === `human:${me.sub}`;
  const resync = useCallback(() => { void syncHistory(store, sid); }, [store, sid]);
  useEffect(() => { resync(); }, [resync]);
  useChannel(`/session/${sid}`, (p) => { const ev = SessionEvent.safeParse(p); if (ev.success) store.getState().applyEvent(ev.data); },
    { as: "staff", onResync: resync });

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    try {
      const r = await fetch(`/api/sessions/${encodeURIComponent(sid)}/messages`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text: body }) });
      if (r.ok) { setText(""); setError(null); resync(); }
      else { setError(r.status === 409 ? "You no longer hold this conversation." : "Message not sent. Try again."); if (r.status === 409) resync(); }
    } catch { setError("Message not sent. Try again."); }
    finally { setSending(false); }
  }

  return (
    <div className="flex flex-col gap-2 text-[13px]">
      <ol aria-live="polite" className="bg-c-panel rounded-[var(--radius-panel)] ring-1 ring-c-line p-3 flex flex-col gap-2 max-h-[55vh] overflow-y-auto">
        {messages.length === 0 && <li className="text-c-muted">No messages yet.</li>}
        {messages.map((m) => (
          <li key={m.id} className={m.role === "system" ? "text-center text-xs text-c-muted" : ""}>
            {m.role === "system" ? systemLine(m, lang) : (
              <>
                <span className="text-[11px] font-bold text-c-muted mr-2">{m.role === "agent" ? m.author ?? WHO.agent : WHO[m.role]}</span>
                <span className="whitespace-pre-wrap">{m.text}</span>
              </>
            )}
          </li>
        ))}
      </ol>
      <form onSubmit={(e) => void send(e)} className="flex gap-2 items-center">
        <input aria-label="Message to the customer" disabled={!holding} value={text} onChange={(e) => setText(e.target.value)} maxLength={2000}
          placeholder={holding ? "Write to the customer…" : "Take over the chat to write"}
          className="flex-1 bg-c-panel ring-1 ring-c-line rounded-[var(--radius-control)] px-3 py-2 disabled:bg-c-canvas focus-visible:outline-2 focus-visible:outline-c-signal" />
        <button disabled={!holding || sending || !text.trim()} className="rounded-[var(--radius-control)] bg-c-signal text-c-panel px-3 py-2 font-bold disabled:opacity-40">Send</button>
      </form>
      {holding && <p className="text-xs text-c-muted">{WRITE_IN[lang]}</p>}
      {error && <p role="alert" className="text-xs text-c-alert">{error}</p>}
    </div>
  );
}
