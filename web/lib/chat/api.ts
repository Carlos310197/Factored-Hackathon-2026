import { z } from "zod";
import { ChatMessage, ChatReply, NewSession, SessionSummary } from "@/lib/contract";
import type { ChatStore } from "./store";

export type HistoryResult = { kind: "ok"; messages: ChatMessage[] } | { kind: "expired" } | { kind: "error" };

export type SendResult = { kind: "reply"; reply: ChatReply } | { kind: "pending" } | { kind: "expired" } | { kind: "ended" } | { kind: "error" };

export const api = {
  async send(text: string, clientId: string): Promise<SendResult> {
    try {
      const res = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: text, client_message_id: clientId }) });
      if (res.status === 401) return { kind: "expired" };
      if (res.status === 202) return { kind: "pending" };
      if (res.status === 409 && (await errorCode(res)) === "session_ended") return { kind: "ended" };
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

async function errorCode(res: Response): Promise<string | undefined> {
  try { return ((await res.json()) as { error?: { code?: string } }).error?.code; } catch { return undefined; }
}

export type CallResult<T> = { kind: "ok"; data: T } | { kind: "expired" } | { kind: "error"; code?: string };

async function call<T>(url: string, schema: z.ZodType<T>, method = "GET"): Promise<CallResult<T>> {
  try {
    const res = await fetch(url, { method, cache: "no-store" });
    if (res.status === 401) return { kind: "expired" };
    if (!res.ok) return { kind: "error", code: await errorCode(res) };
    const parsed = schema.safeParse((await res.json()).data);
    return parsed.success ? { kind: "ok", data: parsed.data } : { kind: "error", code: undefined };
  } catch {
    return { kind: "error" };
  }
}

/** The customer's own conversations: list, hide a past one, end the current one, start a new one. */
export const sessionsApi = {
  list: () => call("/api/customer/sessions", SessionSummary.array()),
  hide: (sid: string) => call(`/api/customer/sessions/${encodeURIComponent(sid)}/hide`, z.object({ hidden: z.literal(true) }), "POST"),
  end: () => call("/api/customer/sessions/end", z.object({ ended: z.literal(true) }), "POST"),
  create: () => call("/api/customer/sessions/new", NewSession, "POST"),
};
