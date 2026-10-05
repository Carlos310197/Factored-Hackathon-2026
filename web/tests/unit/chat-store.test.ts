import { describe, expect, it } from "vitest";
import type { ChatMessage, ChatReply } from "@/lib/contract";
import { createChatStore } from "@/lib/chat/store";

const msg = (o: Partial<ChatMessage> & Pick<ChatMessage, "id" | "role" | "cursor">): ChatMessage => ({ text: "", ts: "t", ...o });
const reply = (o: Partial<ChatReply> = {}): ChatReply =>
  ({ reply_text: "Tu saldo es USD 1,240.50", language: "es", awaiting: "none", options: [], refs: [], data_as_of: "2026-06-17", turn_id: "TRN-1", ...o });

describe("chat store", () => {
  it("dedupes a reply that arrives by POST and by push", () => {
    const s = createChatStore();
    s.getState().sendOptimistic("cm-1", "saldo");
    s.getState().applyReply("cm-1", reply());
    expect(s.getState().messages.map((m) => [m.role, m.status])).toEqual([["customer", "sending"], ["assistant", "provisional"]]);
    s.getState().applyEvent({ type: "message", id: "cm-1", cursor: "2026-09-30T10:00:00.000000+00:00#cm-1", role: "customer", text: "saldo", turn_id: "TRN-1", ts: "t" });
    s.getState().applyEvent({ type: "message", id: "MSG-9", cursor: "2026-09-30T10:00:01.000000+00:00#MSG-9", role: "assistant",
      text: "Tu saldo es USD 1,240.50", turn_id: "TRN-1", meta: { awaiting: "none" }, ts: "t" });
    s.getState().merge([msg({ id: "MSG-9", role: "assistant", cursor: "2026-09-30T10:00:01.000000+00:00#MSG-9", text: "Tu saldo es USD 1,240.50", turn_id: "TRN-1" })]);
    const m = s.getState().messages;
    expect(m.map((x) => x.id)).toEqual(["cm-1", "MSG-9"]);
    expect(m.every((x) => x.status === undefined)).toBe(true);
    expect(s.getState().cursor).toBe("2026-09-30T10:00:01.000000+00:00#MSG-9");
  });
  it("tracks awaiting from the latest assistant message and control from control events", () => {
    const s = createChatStore();
    s.getState().merge([msg({ id: "a", role: "assistant", cursor: "1", meta: { awaiting: "confirmation" } })]);
    expect(s.getState().awaiting).toBe("confirmation");
    s.getState().applyEvent({ type: "control", control: "human:agent.ana", agent_name: "Ana R." });
    expect(s.getState().control).toBe("human:agent.ana");
    expect(s.getState().awaiting).toBe("human");
  });
  it("keeps the failed message for a retry with the same client id", () => {
    const s = createChatStore();
    s.getState().sendOptimistic("cm-2", "hola");
    s.getState().fail("cm-2");
    expect(s.getState().failed).toEqual({ clientId: "cm-2", text: "hola" });
    expect(s.getState().running).toBe(false);
  });
  it("orders by cursor even when history arrives out of order", () => {
    const s = createChatStore();
    s.getState().merge([msg({ id: "b", role: "assistant", cursor: "2" }), msg({ id: "a", role: "customer", cursor: "1" })]);
    expect(s.getState().messages.map((m) => m.id)).toEqual(["a", "b"]);
  });
  it("keeps a pending send after stored history", () => {
    const s = createChatStore();
    s.getState().merge([msg({ id: "a", role: "customer", cursor: "2026-09-30T10:00:00.000000+00:00#a" })]);
    s.getState().sendOptimistic("cm-3", "nuevo");
    expect(s.getState().messages.map((m) => m.id)).toEqual(["a", "cm-3"]);
  });
  it("a pushed assistant message ends a turn the POST answered with 202", () => {
    const s = createChatStore();
    s.getState().sendOptimistic("cm-1", "hola");
    expect(s.getState().running).toBe(true);
    s.getState().merge([msg({ id: "old", role: "assistant", cursor: "0" })]);  // unseen history counts too
    expect(s.getState().running).toBe(false);
    s.getState().sendOptimistic("cm-2", "otra");
    s.getState().merge([msg({ id: "old", role: "assistant", cursor: "0" })]);  // already known: no change
    expect(s.getState().running).toBe(true);
    s.getState().applyEvent({ type: "message", id: "e1", cursor: "5", role: "system", text: "fallo", meta: { error_code: "agent_failed" }, ts: "t" });
    expect(s.getState().running).toBe(false);
  });
  it("a provisional reply sorts directly after its own question", () => {
    const s = createChatStore();
    s.getState().sendOptimistic("cm-1", "uno");
    s.getState().sendOptimistic("cm-2", "dos");
    s.getState().applyReply("cm-1", reply());
    expect(s.getState().messages.map((m) => m.id)).toEqual(["cm-1", "reply:TRN-1", "cm-2"]);
  });
});
