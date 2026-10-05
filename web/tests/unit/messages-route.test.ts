import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ customerFrom: vi.fn(), staffFrom: vi.fn(), getSession: vi.fn(), listMessages: vi.fn(), appendMessage: vi.fn() }));
vi.mock("@/lib/server/session", () => ({ customerFrom: m.customerFrom, staffFrom: m.staffFrom }));
vi.mock("@/lib/server/sessions", () => ({ getSession: m.getSession }));
vi.mock("@/lib/server/messages", () => ({ listMessages: m.listMessages, appendMessage: m.appendMessage }));

const params = (sid: string) => ({ params: Promise.resolve({ sid }) });
const get = (sid: string) => new NextRequest(`http://localhost/api/sessions/${sid}/messages`);
const SESSION = { session_id: "S-1", customer_id: "CLI-A", language: "es", control: "agent" };

beforeEach(() => { vi.resetAllMocks(); m.listMessages.mockResolvedValue([]); });

describe("GET history", () => {
  it("returns the owner's history", async () => {
    m.customerFrom.mockResolvedValue({ sub: "CLI-A", sid: "S-1" });
    m.getSession.mockResolvedValue(SESSION);
    const { GET } = await import("@/app/api/sessions/[sid]/messages/route");
    expect((await GET(get("S-1"), params("S-1"))).status).toBe(200);
  });
  it("history for a session owned by someone else is not_found", async () => {
    m.customerFrom.mockResolvedValue({ sub: "CLI-EVIL", sid: "S-1" });
    m.staffFrom.mockResolvedValue(null);
    m.getSession.mockResolvedValue(SESSION);
    const { GET } = await import("@/app/api/sessions/[sid]/messages/route");
    const res = await GET(get("S-1"), params("S-1"));
    expect(res.status).toBe(404);
    expect(m.listMessages).not.toHaveBeenCalled();
  });
  it("a customer asking for another sid than their token's is not_found", async () => {
    m.customerFrom.mockResolvedValue({ sub: "CLI-A", sid: "S-1" });
    m.staffFrom.mockResolvedValue(null);
    m.getSession.mockResolvedValue({ ...SESSION, session_id: "S-2" });
    const { GET } = await import("@/app/api/sessions/[sid]/messages/route");
    expect((await GET(get("S-2"), params("S-2"))).status).toBe(404);
  });
  it("any agent can read", async () => {
    m.customerFrom.mockResolvedValue(null);
    m.staffFrom.mockResolvedValue({ sub: "agent.ana", name: "Ana R." });
    m.getSession.mockResolvedValue(SESSION);
    const { GET } = await import("@/app/api/sessions/[sid]/messages/route");
    expect((await GET(get("S-1"), params("S-1"))).status).toBe(200);
  });
});

describe("POST agent message", () => {
  const post = (text: string) => new NextRequest("http://localhost/api/sessions/S-1/messages", { method: "POST",
    body: JSON.stringify({ text }), headers: { "content-type": "application/json" } });
  it("needs the takeover held by this agent", async () => {
    m.staffFrom.mockResolvedValue({ sub: "agent.luis", name: "Luis M." });
    m.getSession.mockResolvedValue({ ...SESSION, control: "human:agent.ana" });
    const { POST } = await import("@/app/api/sessions/[sid]/messages/route");
    expect((await POST(post("hola"), params("S-1"))).status).toBe(409);
    m.staffFrom.mockResolvedValue({ sub: "agent.ana", name: "Ana R." });
    m.appendMessage.mockResolvedValue({ id: "x" });
    expect((await POST(post("hola"), params("S-1"))).status).toBe(201);
    expect(m.appendMessage).toHaveBeenCalledWith("S-1", { role: "agent", text: "hola", author: "Ana R." });
  });
});
