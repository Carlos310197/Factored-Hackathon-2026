import { ChatMessage, ChatReply } from "@/lib/contract";

export type SendResult = { kind: "reply"; reply: ChatReply } | { kind: "pending" } | { kind: "expired" } | { kind: "error" };

export const api = {
  async send(text: string, clientId: string): Promise<SendResult> {
    try {
      const res = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: text, client_message_id: clientId }) });
      if (res.status === 401) return { kind: "expired" };
      if (res.status === 202) return { kind: "pending" };
      if (!res.ok) return { kind: "error" };
      return { kind: "reply", reply: ChatReply.parse((await res.json()).data) };
    } catch {
      return { kind: "error" };
    }
  },
  async history(sid: string, after?: string): Promise<ChatMessage[]> {
    const q = after ? `?after=${encodeURIComponent(after)}` : "";
    const res = await fetch(`/api/sessions/${encodeURIComponent(sid)}/messages${q}`, { cache: "no-store" });
    if (!res.ok) return [];
    return ChatMessage.array().parse((await res.json()).data);
  },
};
