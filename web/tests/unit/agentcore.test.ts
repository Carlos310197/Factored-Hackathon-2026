import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentError, invokeAgent, runtimeSessionId } from "@/lib/server/agentcore";

afterEach(() => vi.unstubAllGlobals());

describe("runtimeSessionId", () => {
  it("is deterministic and at least 33 characters", () => {
    expect(runtimeSessionId("S-1")).toBe(runtimeSessionId("S-1"));
    expect(runtimeSessionId("S-1").length).toBeGreaterThanOrEqual(33);
    expect(runtimeSessionId("S-1")).not.toBe(runtimeSessionId("S-2"));
  });
});

describe("invokeAgent", () => {
  it("sends the bearer token, runtime session id and message-id header, and parses the reply", async () => {
    const fetchMock = vi.fn(async () => Response.json({ reply_text: "ok", language: "es", awaiting: "none", turn_id: "TRN-1" }));
    vi.stubGlobal("fetch", fetchMock);
    const r = await invokeAgent({ token: "tok", sid: "S-1", message: "saldo", clientMessageId: "cm-12345678", lang: "es" });
    expect(r.turn_id).toBe("TRN-1");
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const h = init.headers as Record<string, string>;
    expect(h.authorization).toBe("Bearer tok");
    expect(h["x-amzn-bedrock-agentcore-runtime-session-id"]).toBe(runtimeSessionId("S-1"));
    expect(h["x-amzn-bedrock-agentcore-runtime-custom-message-id"]).toBe("cm-12345678");
    expect(JSON.parse(String(init.body))).toEqual({ message: "saldo", client_message_id: "cm-12345678", lang: "es" });
  });
  it("maps timeouts and upstream errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw Object.assign(new Error("t"), { name: "TimeoutError" }); }));
    await expect(invokeAgent({ token: "t", sid: "S", message: "m", clientMessageId: "cm-12345678", lang: "es" }))
      .rejects.toMatchObject({ kind: "timeout" });
    vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 500 })));
    await expect(invokeAgent({ token: "t", sid: "S", message: "m", clientMessageId: "cm-12345678", lang: "es" }))
      .rejects.toBeInstanceOf(AgentError);
  });
  const call = () => invokeAgent({ token: "t", sid: "S", message: "m", clientMessageId: "cm-12345678", lang: "es" });
  it("maps a malformed or non-JSON 200 to upstream", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ nope: 1 })));
    await expect(call()).rejects.toMatchObject({ kind: "upstream" });
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>", { status: 200 })));
    await expect(call()).rejects.toMatchObject({ kind: "upstream" });
  });
  it("maps 401/403 to auth", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("no", { status: 403 })));
    await expect(call()).rejects.toMatchObject({ kind: "auth" });
  });
});
