import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ staffFrom: vi.fn(), listHandoffs: vi.fn(), getHandoff: vi.fn(), claim: vi.fn(),
  takeover: vi.fn(), returnToAssistant: vi.fn(), resolve: vi.fn(), getSession: vi.fn() }));
vi.mock("@/lib/server/session", () => ({ staffFrom: m.staffFrom }));
vi.mock("@/lib/server/sessions", () => ({ getSession: m.getSession }));
vi.mock("@/lib/server/handoffs", () => ({ listHandoffs: m.listHandoffs, getHandoff: m.getHandoff, claim: m.claim,
  takeover: m.takeover, returnToAssistant: m.returnToAssistant, resolve: m.resolve }));
vi.mock("@/lib/server/ddb", () => ({ ConflictError: class ConflictError extends Error {}, NotFoundError: class NotFoundError extends Error {} }));

const ANA = { sub: "agent.ana", name: "Ana R.", token: "t", sid: "STAFF-1", exp: 0 };
const row = (id: string, status: string, claimed_by?: string) => ({ handoff_id: id, session_id: "S", status, priority: "high",
  reason_codes: [], language: "es", created_at: "c", claimed_by });

beforeEach(() => { vi.resetAllMocks(); m.staffFrom.mockResolvedValue(ANA); });

describe("GET /api/handoffs", () => {
  it("is 401 without staff", async () => {
    m.staffFrom.mockResolvedValue(null);
    const { GET } = await import("@/app/api/handoffs/route");
    expect((await GET(new NextRequest("http://localhost/api/handoffs"))).status).toBe(401);
  });
  it("mine keeps only my claimed, in-takeover and returned cases", async () => {
    m.listHandoffs.mockResolvedValue([row("H1", "claimed", "agent.ana"), row("H2", "in_takeover", "agent.luis"), row("H3", "returned", "agent.ana")]);
    const { GET } = await import("@/app/api/handoffs/route");
    const res = await GET(new NextRequest("http://localhost/api/handoffs?filter=mine"));
    expect(m.listHandoffs).toHaveBeenCalledWith(["claimed", "in_takeover", "returned"]);
    expect((await res.json()).data.map((r: { handoff_id: string }) => r.handoff_id)).toEqual(["H1", "H3"]);
  });
});

describe("POST /api/handoffs/[id]/[action]", () => {
  const post = (body?: unknown) => new NextRequest("http://localhost/x", { method: "POST", body: body ? JSON.stringify(body) : "{}",
    headers: { "content-type": "application/json" } });
  const ctx = (id: string, action: string) => ({ params: Promise.resolve({ id, action }) });

  it("dispatches each action with the signed-in agent", async () => {
    const { POST } = await import("@/app/api/handoffs/[id]/[action]/route");
    m.claim.mockResolvedValue({ status: "claimed" });
    m.takeover.mockResolvedValue({ status: "in_takeover" });
    m.returnToAssistant.mockResolvedValue({ status: "returned" });
    m.resolve.mockResolvedValue({ status: "resolved" });
    await POST(post(), ctx("H1", "claim"));
    await POST(post(), ctx("H1", "takeover"));
    await POST(post(), ctx("H1", "return"));
    await POST(post({ code: "resolved_by_agent", note: "ok" }), ctx("H1", "resolve"));
    expect(m.claim).toHaveBeenCalledWith("H1", "agent.ana");
    expect(m.takeover).toHaveBeenCalledWith("H1", "agent.ana", "Ana R.");
    expect(m.returnToAssistant).toHaveBeenCalledWith("H1", "agent.ana");
    expect(m.resolve).toHaveBeenCalledWith("H1", "agent.ana", "resolved_by_agent", "ok");
  });
  it("maps NotFoundError to 404", async () => {
    const { NotFoundError } = await import("@/lib/server/ddb");
    const { POST } = await import("@/app/api/handoffs/[id]/[action]/route");
    m.claim.mockRejectedValue(new NotFoundError("x"));
    expect((await POST(post(), ctx("H1", "claim"))).status).toBe(404);
  });
  it("maps ConflictError to 409, unknown actions to 404 and a bad resolve body to 400", async () => {
    const { ConflictError } = await import("@/lib/server/ddb");
    const { POST } = await import("@/app/api/handoffs/[id]/[action]/route");
    m.returnToAssistant.mockRejectedValue(new ConflictError("x"));
    expect((await POST(post(), ctx("H1", "return"))).status).toBe(409);
    expect((await POST(post(), ctx("H1", "delete"))).status).toBe(404);
    expect((await POST(post({ code: "nope" }), ctx("H1", "resolve"))).status).toBe(400);
  });
});

describe("GET /api/handoffs/[id]", () => {
  it("returns the packet with the session's control", async () => {
    m.getHandoff.mockResolvedValue({ handoff_id: "H1", session_id: "S-1" });
    m.getSession.mockResolvedValue({ control: "human:agent.ana" });
    const { GET } = await import("@/app/api/handoffs/[id]/route");
    const res = await GET(new NextRequest("http://localhost/api/handoffs/H1"), { params: Promise.resolve({ id: "H1" }) });
    expect((await res.json()).data).toEqual({ packet: { handoff_id: "H1", session_id: "S-1" }, control: "human:agent.ana" });
  });
});
