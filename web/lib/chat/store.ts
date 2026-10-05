import { createStore } from "zustand/vanilla";
import type { Awaiting, ChatMessage, ChatReply, SessionEvent } from "@/lib/contract";

export type ViewMessage = ChatMessage & { status?: "sending" | "provisional" };
export interface ChatState {
  messages: ViewMessage[]; cursor: string | null; running: boolean; pending: string[]; awaiting: Awaiting; control: string;
  failed: { clientId: string; text: string } | null; expired: boolean;
  sendOptimistic(clientId: string, text: string): void;
  applyReply(clientId: string, reply: ChatReply): void;
  merge(incoming: ChatMessage[]): void;
  applyEvent(ev: SessionEvent): void;
  fail(clientId: string): void;
  expire(): void;
}

const PENDING = "~";  // optimistic/provisional rows sort after every stored cursor

function derive(messages: ViewMessage[], control: string): Pick<ChatState, "awaiting" | "cursor"> {
  const stored = messages.filter((m) => !m.status);
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const awaiting: Awaiting = control !== "agent" ? "human" : lastAssistant?.meta?.awaiting ?? "none";
  return { awaiting, cursor: stored.at(-1)?.cursor ?? null };
}

function upsert(current: ViewMessage[], incoming: ChatMessage[]): ViewMessage[] {
  const byId = new Map(current.map((m) => [m.id, m]));
  for (const m of incoming) {
    byId.set(m.id, { ...m, status: undefined });
    if (m.role === "assistant" && m.turn_id) byId.delete(`reply:${m.turn_id}`);  // drop the provisional POST copy
  }
  return [...byId.values()].sort((a, b) => (a.cursor < b.cursor ? -1 : a.cursor > b.cursor ? 1 : 0));
}

/** Turn-scoped settling for turns the POST answered with 202. An unseen assistant (or async-failure system) message
 *  settles them only when its cursor sorts after the LATEST pending question's stored cursor; the stored copy of a reply
 *  that already has a provisional `reply:<turn_id>` never settles anything. Returns the ids still pending. */
function settle(before: ViewMessage[], after: ViewMessage[], pending: string[], incoming: ChatMessage[]): string[] {
  if (!pending.length) return pending;
  const latest = pending.map((id) => after.find((m) => m.id === id)?.cursor).filter((c): c is string => !!c).sort().at(-1);
  if (!latest || latest.startsWith(PENDING)) return pending;
  const ends = incoming.some((m) => (m.role === "assistant" || (m.role === "system" && m.meta?.error_code))
    && !before.some((k) => k.id === m.id) && !(m.turn_id && before.some((k) => k.id === `reply:${m.turn_id}`)) && m.cursor > latest);
  return ends ? [] : pending;
}

export function createChatStore() {
  return createStore<ChatState>((set) => ({
    messages: [], cursor: null, running: false, pending: [], awaiting: "none", control: "agent", failed: null, expired: false,

    sendOptimistic: (clientId, text) => set((s) => {
      const messages = upsert(s.messages.filter((m) => m.id !== clientId), [])
        .concat({ id: clientId, cursor: `${PENDING}${Date.now()}#${clientId}`, role: "customer", text, ts: new Date().toISOString(), status: "sending" });
      return { messages, running: true, pending: [...s.pending.filter((id) => id !== clientId), clientId], failed: null };
    }),

    applyReply: (clientId, reply) => set((s) => {
      const pending = s.pending.filter((id) => id !== clientId);
      if (reply.awaiting === "human" || !reply.turn_id) return { running: pending.length > 0, pending, ...derive(s.messages, s.control) };
      const id = `reply:${reply.turn_id}`;
      const q = s.messages.find((m) => m.id === clientId)?.cursor;
      const already = s.messages.some((m) => m.role === "assistant" && m.turn_id === reply.turn_id && !m.status);
      const messages = already ? s.messages : [...s.messages.filter((m) => m.id !== id), {
        id, cursor: q ? `${q}~r` : `${PENDING}${Date.now()}#${id}`, role: "assistant" as const, text: reply.reply_text, turn_id: reply.turn_id, ts: new Date().toISOString(),
        meta: { awaiting: reply.awaiting, options: reply.options, refs: reply.refs, summary: reply.summary, data_as_of: reply.data_as_of ?? undefined },
        status: "provisional" as const }].sort((a, b) => (a.cursor < b.cursor ? -1 : a.cursor > b.cursor ? 1 : 0));
      return { messages, running: pending.length > 0, pending, ...derive(messages, s.control) };
    }),

    merge: (incoming) => set((s) => {
      const messages = upsert(s.messages, incoming);
      const pending = settle(s.messages, messages, s.pending, incoming);
      return { messages, pending, running: pending.length > 0, ...derive(messages, s.control) };
    }),

    applyEvent: (ev) => set((s) => {
      if (ev.type === "control") return { control: ev.control, ...derive(s.messages, ev.control) };
      const { type: _t, ...m } = ev;
      void _t;
      const messages = upsert(s.messages, [m]);
      const control = m.role === "system" && m.meta?.control ? m.meta.control : s.control;
      const pending = settle(s.messages, messages, s.pending, [m]);
      return { messages, control, pending, running: pending.length > 0, ...derive(messages, control) };
    }),

    fail: (clientId) => set((s) => {
      const m = s.messages.find((x) => x.id === clientId);
      const pending = s.pending.filter((id) => id !== clientId);
      return { running: pending.length > 0, pending, failed: m ? { clientId, text: m.text } : null, messages: s.messages.filter((x) => x.id !== clientId) };
    }),

    expire: () => set({ expired: true, running: false, pending: [] }),
  }));
}
export type ChatStore = ReturnType<typeof createChatStore>;
