import { describe, expect, it } from "vitest";
import { ChatReply, HandoffPacket, QueueEvent, SessionEvent, TraceEvent } from "@/lib/contract";

describe("contract", () => {
  it("parses an agent reply with defaults and summary", () => {
    const r = ChatReply.parse({ reply_text: "Resumen", language: "es", awaiting: "confirmation", turn_id: "TRN-1",
      summary: { merchant: "Éxito", date: "2026-06-03", amount: 184900, currency: "COP", reason_code: "duplicate_charge" } });
    expect(r.options).toEqual([]) ;
    expect(r.refs).toEqual([]);
    expect(r.summary?.currency).toBe("COP");
  });
  it("accepts awaiting human and rejects unknown awaiting values", () => {
    expect(ChatReply.parse({ reply_text: "", language: "pt", awaiting: "human", turn_id: null }).awaiting).toBe("human");
    expect(() => ChatReply.parse({ reply_text: "", language: "es", awaiting: "maybe" })).toThrow();
  });
  it("parses session, queue and trace channel events", () => {
    expect(SessionEvent.parse({ type: "message", id: "M", cursor: "c", role: "agent", text: "Hola", author: "Ana R.", ts: "t" }).type).toBe("message");
    expect(SessionEvent.parse({ type: "control", control: "human:agent.ana", agent_name: "Ana R." }).type).toBe("control");
    expect(QueueEvent.parse({ type: "handoff", handoff_id: "H", session_id: "S", status: "open", priority: "critical",
      reason_codes: ["reports_unauthorized_use"], language: "es", created_at: "c" }).priority).toBe("critical");
    expect(TraceEvent.parse({ type: "turn_complete", turn_id: "TRN-1" }).type).toBe("turn_complete");
  });
  it("parses a handoff.v1 packet with lifecycle fields", () => {
    const p = HandoffPacket.parse({ schema_version: "handoff.v1", handoff_id: "HND-1", created_at: "2026-09-30T10:00:00Z",
      status: "claimed", claimed_by: "agent.ana", session_id: "S-1", customer_id: "CLI-1", language: "es",
      data_as_of: "2026-06-17", priority: "critical", reason_codes: ["reports_unauthorized_use"],
      customer_request: { original: "No reconozco", en: "I don't recognize" },
      verified_facts: [{ fact: "Amazon USD 420.00", receipt_id: "r-1" }],
      actions_taken: [{ action: "dispute_drafted", result: "pending_review", receipt_id: "r-2" }],
      decisions: [{ question: "reports_unauthorized_use", value: 0.88, question_set: "understand.v1", thresholds: "thresholds.v1" }],
      policy_checks: [{ rule: "within_60_days", passed: true }], open_questions: ["¿Tiene la tarjeta?"], transcript_ref: "session:S-1" });
    expect(p.status).toBe("claimed");
  });
});
