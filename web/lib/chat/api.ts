import { ChatMessage, ChatReply } from "@/lib/contract";
import type { ChatStore } from "./store";

export type HistoryResult = { kind: "ok"; messages: ChatMessage[] } | { kind: "expired" } | { kind: "error" };

export type SendResult = { kind: "reply"; reply: ChatReply } | { kind: "pending" } | { kind: "expired" } | { kind: "error" };

export const api = {
  async send(text: string, clientId: string): Promise<SendResult> {
    try {
      const res = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: text, client_message_id: clientId }) });
      if (res.status === 401) return { kind: "expired" };
      if (res.status === 202) return { kind: "pending" };
      if (!res.ok) return { kind: "error" };
      const parsed = ChatReply.safeParse((await res.json()).data);
      return parsed.success ? { kind: "reply", reply: parsed.data } : { kind: "error" };
    } catch {
      return { kind: "error" };
    }
  },
  async history(sid: string, after?: string): Promise<HistoryResult> {
    try {
      const q = after ? `?after=${encodeURIComponent(after)}` : "";
      const res = await fetch(`/api/sessions/${encodeURIComponent(sid)}/messages${q}`, { cache: "no-store" });
      if (res.status === 401) return { kind: "expired" };
      if (!res.ok) return { kind: "error" };
      const parsed = ChatMessage.array().safeParse((await res.json()).data);
      return parsed.success ? { kind: "ok", messages: parsed.data } : { kind: "error" };
    } catch {
      return { kind: "error" };
    }
  },
};

/** Load history after the store's cursor and merge it; a 401 expires the session. */
export async function syncHistory(store: ChatStore, sid: string): Promise<void> {
  const r = await api.history(sid, store.getState().cursor ?? undefined);
  if (r.kind === "ok") store.getState().merge(r.messages);
  else if (r.kind === "expired") store.getState().expire();
}
