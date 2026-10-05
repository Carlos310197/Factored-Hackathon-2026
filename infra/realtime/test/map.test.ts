import { describe, expect, it } from "vitest";
import { tableKind, toEvents } from "../publisher/map";

const arn = (t: string) => `arn:aws:dynamodb:us-east-2:1:table/bankagent-dev-${t}/stream/2026`;

describe("tableKind", () => {
  it("recognises the three tables and nothing else", () => {
    expect(tableKind(arn("handoffs"))).toBe("handoffs");
    expect(tableKind(arn("decision_records"))).toBe("decision_records");
    expect(tableKind(arn("conversation_messages"))).toBe("conversation_messages");
    expect(tableKind(arn("disputes"))).toBeNull();
  });
});

describe("toEvents", () => {
  it("maps a message insert to /session/<sid>", () => {
    const img = { session_id: "S-1", sk: "2026-09-30T10:00:00.000000+00:00#MSG-1", kind: "message", message_id: "MSG-1",
      role: "assistant", text: "hola", turn_id: "TRN-1", meta: { awaiting: "none" }, ts: "2026-09-30T10:00:00.000000+00:00" };
    expect(toEvents("conversation_messages", img, "INSERT")).toEqual([{ channel: "/session/S-1", payload: {
      type: "message", id: "MSG-1", cursor: img.sk, role: "assistant", text: "hola", turn_id: "TRN-1",
      author: undefined, meta: { awaiting: "none" }, ts: img.ts } }]);
  });
  it("adds a control event for system rows that change control", () => {
    const img = { session_id: "S-1", sk: "x#M", kind: "message", message_id: "M", role: "system", text: "Ana se unió",
      meta: { control: "human:agent.ana", agent_name: "Ana R." }, ts: "t" };
    const out = toEvents("conversation_messages", img, "INSERT");
    expect(out.map((e) => e.payload.type)).toEqual(["message", "control"]);
    expect(out[1].payload).toEqual({ type: "control", control: "human:agent.ana", agent_name: "Ana R." });
  });
  it("ignores idempotency markers and modifications of messages", () => {
    expect(toEvents("conversation_messages", { session_id: "S-1", sk: "~idem#m", kind: "idem" }, "INSERT")).toEqual([]);
    expect(toEvents("conversation_messages", { session_id: "S-1", sk: "~idem#m", kind: "idem", state: "done" }, "MODIFY")).toEqual([]);
  });
  it("maps handoff inserts and modifications to /queue/all", () => {
    const img = { handoff_id: "HND-1", session_id: "S-1", status: "claimed", priority: "critical",
      reason_codes: ["reports_unauthorized_use"], language: "es", created_at: "c", claimed_by: "agent.ana", verified_facts: [] };
    expect(toEvents("handoffs", img, "MODIFY")).toEqual([{ channel: "/queue/all", payload: {
      type: "handoff", handoff_id: "HND-1", session_id: "S-1", status: "claimed", priority: "critical",
      reason_codes: ["reports_unauthorized_use"], language: "es", created_at: "c", claimed_by: "agent.ana" } }]);
  });
  it("maps decision records to slim trace events and turn_end to turn_complete", () => {
    const rec = { session_id: "S-1", sk: "TRN-1#0003", turn_id: "TRN-1", seq: 3, node: "understand", kind: "jev", payload: { big: true } };
    expect(toEvents("decision_records", rec, "INSERT").filter((e) => e.channel === "/trace/S-1")).toEqual([{ channel: "/trace/S-1",
      payload: { type: "record", turn_id: "TRN-1", seq: 3, node: "understand", kind: "jev" } }]);
    const end = { ...rec, node: "turn", kind: "turn_end", seq: 9 };
    expect(toEvents("decision_records", end, "INSERT").map((e) => e.payload.type)).toEqual(["record", "turn_complete"]);
  });
  it("emits payload-free progress stages to the customer session channel", () => {
    const rec = (node: string, kind: string) => ({ session_id: "S-1", sk: "x", turn_id: "TRN-1", seq: 1, node, kind, payload: { secret: "4111" } });
    const prog = (node: string, kind: string) => toEvents("decision_records", rec(node, kind), "INSERT").filter((e) => e.channel === "/session/S-1");
    expect(prog("load_context", "state")[0].payload).toEqual({ type: "progress", turn_id: "TRN-1", stage: "understand" });
    expect(prog("understand", "jev")[0].payload.stage).toBe("understand");
    expect(prog("router", "route")[0].payload.stage).toBe("decide");
    expect(prog("tools", "tool_call")[0].payload.stage).toBe("act");
    expect(prog("reply", "jev")[0].payload.stage).toBe("verify");
    expect(prog("turn", "turn_end")).toEqual([]);
    expect(JSON.stringify(prog("tools", "tool_call"))).not.toContain("4111");
  });
  it("ignores removals (TTL expiry)", () => {
    expect(toEvents("handoffs", { handoff_id: "H" }, "REMOVE")).toEqual([]);
  });
});
