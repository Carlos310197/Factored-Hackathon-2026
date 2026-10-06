import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({
  customerFrom: vi.fn(), e2eNewSession: vi.fn(), listCustomerSessions: vi.fn(), endSession: vi.fn(), hideSession: vi.fn(),
  appendMessage: vi.fn(), newSession: vi.fn(), customer: vi.fn(), warmAgent: vi.fn(),
}));
vi.mock("next/server", async (orig) => ({ ...(await orig<typeof import("next/server")>()), after: (fn: () => unknown) => { void fn(); } }));
vi.mock("@/lib/server/session", async (orig) => ({ ...(await orig<typeof import("@/lib/server/session")>()),
  customerFrom: m.customerFrom, e2eNewSession: m.e2eNewSession }));
vi.mock("@/lib/server/sessions", () => ({ listCustomerSessions: m.listCustomerSessions, endSession: m.endSession, hideSession: m.hideSession }));
vi.mock("@/lib/server/messages", () => ({ appendMessage: m.appendMessage }));
vi.mock("@/lib/server/idp", async (orig) => ({ ...(await orig<typeof import("@/lib/server/idp")>()), idp: { newSession: m.newSession } }));
vi.mock("@/lib/server/jwt", async (orig) => ({ ...(await orig<typeof import("@/lib/server/jwt")>()), verifier: () => ({ customer: m.customer }) }));
vi.mock("@/lib/server/agentcore", () => ({ warmAgent: m.warmAgent }));

const CUST = { token: "tok-old", sub: "CLI-A", sid: "S-CUR", lang: "es", scopes: [], exp: 0 };
const req = (path: string, method = "GET") => new NextRequest(`http://localhost${path}`, { method });
const ROW = (sid: string, over = {}) => ({ session_id: sid, created_at: "2026-10-05T10:00:00.000000+00:00", language: "es", ended: false, preview: "hola", ...over });

beforeEach(() => { vi.resetAllMocks(); });

describe("GET /api/customer/sessions", () => {
  it("is 401 without a customer", async () => {
    m.customerFrom.mockResolvedValue(null);
    const { GET } = await import("@/app/api/customer/sessions/route");
    expect((await GET(req("/api/customer/sessions"))).status).toBe(401);
  });
  it("lists the token's customer's conversations and marks the current one", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    m.listCustomerSessions.mockResolvedValue([ROW("S-CUR"), ROW("S-OLD", { ended: true })]);
    const { GET } = await import("@/app/api/customer/sessions/route");
    const body = await (await GET(req("/api/customer/sessions"))).json();
    expect(m.listCustomerSessions).toHaveBeenCalledWith("CLI-A");
    expect(body.data.map((x: { session_id: string; current: boolean }) => [x.session_id, x.current])).toEqual([["S-CUR", true], ["S-OLD", false]]);
  });
  it("puts the current conversation first even before its first turn has created it", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    m.listCustomerSessions.mockResolvedValue([ROW("S-OLD")]);
    const { GET } = await import("@/app/api/customer/sessions/route");
    const body = await (await GET(req("/api/customer/sessions"))).json();
    expect(body.data[0]).toMatchObject({ session_id: "S-CUR", current: true, ended: false, preview: null, language: "es" });
    expect(body.data).toHaveLength(2);
  });
});

describe("POST /api/customer/sessions/end", () => {
  it("ends the token's conversation", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    m.endSession.mockResolvedValue({ control: "agent" });
    const { POST } = await import("@/app/api/customer/sessions/end/route");
    const res = await POST(req("/api/customer/sessions/end", "POST"));
    expect(res.status).toBe(200);
    expect(m.endSession).toHaveBeenCalledWith("S-CUR", "CLI-A", "es");
    expect(m.appendMessage).not.toHaveBeenCalled();
  });
  it("tells the person holding the chat that the customer left", async () => {
    m.customerFrom.mockResolvedValue({ ...CUST, lang: "pt" });
    m.endSession.mockResolvedValue({ control: "human:agent.ana" });
    const { POST } = await import("@/app/api/customer/sessions/end/route");
    await POST(req("/api/customer/sessions/end", "POST"));
    expect(m.appendMessage).toHaveBeenCalledWith("S-CUR", expect.objectContaining({ role: "system", text: expect.stringMatching(/encerrou a conversa/) }));
  });
});

describe("POST /api/customer/sessions/new", () => {
  it("ends the current conversation and swaps the cookie for a new session from the IdP", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    m.endSession.mockResolvedValue({ control: "agent" });
    m.e2eNewSession.mockReturnValue(null);
    m.newSession.mockResolvedValue({ access_token: "tok-new", expires_in: 600, lang: "es" });
    m.customer.mockResolvedValue({ ...CUST, token: "tok-new", sid: "S-NEW" });
    const { POST } = await import("@/app/api/customer/sessions/new/route");
    const res = await POST(req("/api/customer/sessions/new", "POST"));
    expect(res.status).toBe(200);
    expect(m.endSession).toHaveBeenCalledWith("S-CUR", "CLI-A", "es");
    expect(m.newSession).toHaveBeenCalledWith("tok-old");
    expect((await res.json()).data).toEqual({ session_id: "S-NEW", lang: "es", expires_in: 600 });
    expect(res.headers.get("set-cookie")).toMatch(/cust_session=tok-new/);
    expect(m.warmAgent).toHaveBeenCalledWith({ token: "tok-new", sid: "S-NEW" });
  });
  it("is 401 when the IdP refuses (expired login)", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    m.endSession.mockResolvedValue({ control: "agent" });
    m.e2eNewSession.mockReturnValue(null);
    const { IdpError } = await import("@/lib/server/idp");
    m.newSession.mockRejectedValue(new IdpError(401));
    const { POST } = await import("@/app/api/customer/sessions/new/route");
    expect((await POST(req("/api/customer/sessions/new", "POST"))).status).toBe(401);
  });
});

describe("POST /api/customer/sessions/:sid/hide", () => {
  const params = (sid: string) => ({ params: Promise.resolve({ sid }) });
  it("refuses the current conversation with 409 current_session", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    const { POST } = await import("@/app/api/customer/sessions/[sid]/hide/route");
    const res = await POST(req("/api/customer/sessions/S-CUR/hide", "POST"), params("S-CUR"));
    expect(res.status).toBe(409);
    expect((await res.json()).error.code).toBe("current_session");
    expect(m.hideSession).not.toHaveBeenCalled();
  });
  it("hides an owned past conversation and is 404 for anyone else's", async () => {
    m.customerFrom.mockResolvedValue(CUST);
    const { NotFoundError } = await import("@/lib/server/ddb");
    m.hideSession.mockResolvedValueOnce(undefined).mockRejectedValueOnce(new NotFoundError("S-X"));
    const { POST } = await import("@/app/api/customer/sessions/[sid]/hide/route");
    const ok = await POST(req("/api/customer/sessions/S-OLD/hide", "POST"), params("S-OLD"));
    expect(ok.status).toBe(200);
    expect(m.hideSession).toHaveBeenCalledWith("S-OLD", "CLI-A");
    expect((await POST(req("/api/customer/sessions/S-X/hide", "POST"), params("S-X"))).status).toBe(404);
  });
});
