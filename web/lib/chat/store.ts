import { createStore } from "zustand/vanilla";
import type { Awaiting, ChatMessage, ChatReply, SessionEvent } from "@/lib/contract";

export type ViewMessage = ChatMessage & { status?: "sending" | "provisional" };
export interface ChatState {
  messages: ViewMessage[]; cursor: string | null; running: boolean; awaiting: Awaiting; control: string;
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
  return [...byId.values()].sort((a, b) => a.cursor.localeCompare(b.cursor));
}

export function createChatStore() {
  return createStore<ChatState>((set) => ({
    messages: [], cursor: null, running: false, awaiting: "none", control: "agent", failed: null, expired: false,

    sendOptimistic: (clientId, text) => set((s) => {
      const messages = upsert(s.messages.filter((m) => m.id !== clientId), [])
        .concat({ id: clientId, cursor: `${PENDING}${Date.now()}#${clientId}`, role: "customer", text, ts: new Date().toISOString(), status: "sending" });
      return { messages, running: true, failed: null };
    }),

    applyReply: (clientId, reply) => set((s) => {
      if (reply.awaiting === "human" || !reply.turn_id) return { running: false, ...derive(s.messages, s.control) };
      const id = `reply:${reply.turn_id}`;
      const already = s.messages.some((m) => m.role === "assistant" && m.turn_id === reply.turn_id && !m.status);
      const messages = already ? s.messages : [...s.messages.filter((m) => m.id !== id), {
        id, cursor: `${PENDING}${Date.now()}#${id}`, role: "assistant" as const, text: reply.reply_text, turn_id: reply.turn_id, ts: new Date().toISOString(),
        meta: { awaiting: reply.awaiting, options: reply.options, refs: reply.refs, summary: reply.summary, data_as_of: reply.data_as_of ?? undefined },
        status: "provisional" as const }];
      void clientId;
      return { messages, running: false, ...derive(messages, s.control) };
    }),

    merge: (incoming) => set((s) => {
      const messages = upsert(s.messages, incoming);
      return { messages, ...derive(messages, s.control) };
    }),

    applyEvent: (ev) => set((s) => {
      if (ev.type === "control") return { control: ev.control, ...derive(s.messages, ev.control) };
      const { type: _t, ...m } = ev;
      void _t;
      const messages = upsert(s.messages, [m]);
      const control = m.role === "system" && m.meta?.control ? m.meta.control : s.control;
      return { messages, control, ...derive(messages, control) };
    }),

    fail: (clientId) => set((s) => {
      const m = s.messages.find((x) => x.id === clientId);
      return { running: false, failed: m ? { clientId, text: m.text } : null, messages: s.messages.filter((x) => x.id !== clientId) };
    }),

    expire: () => set({ expired: true, running: false }),
  }));
}
export type ChatStore = ReturnType<typeof createChatStore>;
