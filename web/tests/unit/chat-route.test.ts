import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({
  customerFrom: vi.fn(), getSession: vi.fn(), appendMessage: vi.fn(), claimMessageId: vi.fn(), invokeAgent: vi.fn(),
}));
vi.mock("next/server", async (orig) => ({ ...(await orig<typeof import("next/server")>()), after: (fn: () => unknown) => { void fn(); } }));
vi.mock("@/lib/server/session", () => ({ customerFrom: m.customerFrom }));
vi.mock("@/lib/server/sessions", () => ({ getSession: m.getSession }));
vi.mock("@/lib/server/messages", () => ({ appendMessage: m.appendMessage, claimMessageId: m.claimMessageId }));
vi.mock("@/lib/server/agentcore", async (orig) => ({ ...(await orig<typeof import("@/lib/server/agentcore")>()), invokeAgent: m.invokeAgent }));

const CUST = { token: "tok", sub: "CLI-A", sid: "S-1", lang: "es", scopes: [], exp: 0 };
const post = (body: unknown) => new NextRequest("http://localhost/api/chat", { method: "POST", body: JSON.stringify(body),
  headers: { "content-type": "application/json" } });

beforeEach(() => { vi.resetAllMocks(); process.env.CHAT_ASYNC = "0"; });

describe("POST /api/chat", () => {
  it("is 401 session_expired without a valid customer cookie", async () => {
    m.customerFrom.mockResolvedValue(null);
    const { POST } = await import("@/app/api/chat/route");
    const res = await POST(post({ message: "hola", client_message_id: "cm-12345678" }));
    expect(res.status).toBe(401);
    expect((await res.json()).error.code).toBe("session_expired");
  });
  it("rejects an empty message and a bad client id with 400", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    const { POST } = await import("@/app/api/chat/route");
    expect((await POST(post({ message: "  ", client_message_id: "cm-12345678" }))).status).toBe(400);
    expect((await POST(post({ message: "hola", client_message_id: "no spaces allowed" }))).status).toBe(400);
  });
  it("skips the runtime while a human holds the session, and stores the message once", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    m.getSession.mockResolvedValue({ session_id: "S-1", customer_id: "CLI-A", language: "es", control: "human:agent.ana" });
    m.claimMessageId.mockResolvedValueOnce(true).mockResolvedValueOnce(false);
    const { POST } = await import("@/app/api/chat/route");
    const first = await (await POST(post({ message: "sí", client_message_id: "cm-12345678" }))).json();
    await POST(post({ message: "sí", client_message_id: "cm-12345678" }));
    expect(first.data.awaiting).toBe("human");
    expect(m.invokeAgent).not.toHaveBeenCalled();
    expect(m.appendMessage).toHaveBeenCalledTimes(1);
    expect(m.appendMessage).toHaveBeenCalledWith("S-1", { role: "customer", text: "sí", id: "cm-12345678" });
  });
  it("invokes the agent with the cookie's token otherwise", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    m.getSession.mockResolvedValue(null);
    m.invokeAgent.mockResolvedValue({ reply_text: "ok", language: "es", awaiting: "none", options: [], refs: [], data_as_of: null, turn_id: "TRN-1" });
    const { POST } = await import("@/app/api/chat/route");
    const res = await POST(post({ message: " saldo ", client_message_id: "cm-12345678" }));
    expect(res.status).toBe(200);
    expect(m.invokeAgent).toHaveBeenCalledWith({ token: "tok", sid: "S-1", message: "saldo", clientMessageId: "cm-12345678", lang: "es" });
  });
  it("turns an agent session_expired reply into 401 and a timeout into 504", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    m.getSession.mockResolvedValue(null);
    m.invokeAgent.mockResolvedValueOnce({ reply_text: "x", language: "es", awaiting: "none", options: [], refs: [], data_as_of: null, turn_id: null, error: "session_expired" });
    const { POST } = await import("@/app/api/chat/route");
    expect((await POST(post({ message: "a", client_message_id: "cm-12345678" }))).status).toBe(401);
    const { AgentError } = await import("@/lib/server/agentcore");
    m.invokeAgent.mockRejectedValueOnce(new AgentError("timeout"));
    expect((await POST(post({ message: "a", client_message_id: "cm-12345679" }))).status).toBe(504);
  });
  it("turns an agent auth error into 401 and a malformed reply into 502", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    m.getSession.mockResolvedValue(null);
    const { POST } = await import("@/app/api/chat/route");
    const { AgentError } = await import("@/lib/server/agentcore");
    m.invokeAgent.mockRejectedValueOnce(new AgentError("auth"));
    const r1 = await POST(post({ message: "a", client_message_id: "cm-12345670" }));
    expect(r1.status).toBe(401);
    expect((await r1.json()).error.code).toBe("session_expired");
    m.invokeAgent.mockRejectedValueOnce(new AgentError("upstream"));
    const r2 = await POST(post({ message: "a", client_message_id: "cm-12345671" }));
    expect(r2.status).toBe(502);
    expect((await r2.json()).error.code).toBe("agent_upstream");
  });
  it("CHAT_ASYNC returns 202 without awaiting, and a failed turn appends a system message", async () => {
    process.env.CHAT_ASYNC = "1";
    m.customerFrom.mockResolvedValue(CUST);
    m.getSession.mockResolvedValue(null);
    const { AgentError } = await import("@/lib/server/agentcore");
    let rejectCall!: (e: unknown) => void;
    m.invokeAgent.mockReturnValue(new Promise((_, rej) => { rejectCall = rej; }));
    const { POST } = await import("@/app/api/chat/route");
    const res = await POST(post({ message: "a", client_message_id: "cm-12345672" }));
    expect(res.status).toBe(202);
    expect(m.appendMessage).not.toHaveBeenCalled();
    rejectCall(new AgentError("timeout"));
    await vi.waitFor(() => expect(m.appendMessage).toHaveBeenCalledWith("S-1", expect.objectContaining({ role: "system" })));
  });
});
