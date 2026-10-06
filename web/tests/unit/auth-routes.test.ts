import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const idp = vi.hoisted(() => ({
  login: vi.fn(), otp: vi.fn(), staffLogin: vi.fn(), realtimeToken: vi.fn(), demoUsers: vi.fn(),
}));
vi.mock("@/lib/server/idp", async (orig) => ({ ...(await orig<typeof import("@/lib/server/idp")>()), idp }));
const session = vi.hoisted(() => ({ customerFrom: vi.fn(), staffFrom: vi.fn() }));
vi.mock("@/lib/server/session", async (orig) => ({ ...(await orig<typeof import("@/lib/server/session")>()), ...session }));

const agent = vi.hoisted(() => ({ warmAgent: vi.fn() }));
vi.mock("@/lib/server/agentcore", async (orig) => ({ ...(await orig<typeof import("@/lib/server/agentcore")>()), ...agent }));
const jwt = vi.hoisted(() => ({ customer: vi.fn() }));
vi.mock("@/lib/server/jwt", async (orig) => ({ ...(await orig<typeof import("@/lib/server/jwt")>()), verifier: () => jwt }));
const afterFns = vi.hoisted(() => [] as (() => unknown)[]);
vi.mock("next/server", async (orig) => ({ ...(await orig<typeof import("next/server")>()), after: (fn: () => unknown) => { afterFns.push(fn); } }));

const req = (url: string, body?: unknown, headers: Record<string, string> = {}) =>
  new NextRequest(`http://localhost${url}`, { method: body ? "POST" : "GET", body: body ? JSON.stringify(body) : undefined,
    headers: { "content-type": "application/json", ...headers } });

beforeEach(() => { vi.resetAllMocks(); process.env.DEMO_MODE = "1"; });

describe("/api/auth/otp", () => {
  it("sets an httpOnly customer cookie with the token lifetime", async () => {
    idp.otp.mockResolvedValue({ access_token: "tok", expires_in: 900, lang: "es" });
    const { POST } = await import("@/app/api/auth/otp/route");
    const res = await POST(req("/api/auth/otp", { login_ticket: "t", otp: "123456" }));
    expect(res.status).toBe(200);
    const c = res.cookies.get("cust_session");
    expect(c?.value).toBe("tok");
    expect(c?.httpOnly).toBe(true);
    expect(c?.maxAge).toBe(900);
    expect(await res.json()).toEqual({ data: { lang: "es", expires_in: 900 } });
  });
  it("warms the conversation's agent session after responding", async () => {
    afterFns.length = 0;
    idp.otp.mockResolvedValue({ access_token: "tok", expires_in: 900, lang: "es" });
    jwt.customer.mockResolvedValue({ token: "tok", sub: "demo01", sid: "S-9", lang: "es", scopes: [], exp: 1 });
    const { POST } = await import("@/app/api/auth/otp/route");
    await POST(req("/api/auth/otp", { login_ticket: "t", otp: "123456" }));
    expect(agent.warmAgent).not.toHaveBeenCalled();  // never delays the login response
    await Promise.all(afterFns.map((fn) => fn()));
    expect(agent.warmAgent).toHaveBeenCalledWith({ token: "tok", sid: "S-9" });
  });
  it("skips the warm-up when the token does not verify, and still logs in", async () => {
    afterFns.length = 0;
    idp.otp.mockResolvedValue({ access_token: "tok", expires_in: 900, lang: "es" });
    jwt.customer.mockRejectedValue(new Error("bad"));
    const { POST } = await import("@/app/api/auth/otp/route");
    expect((await POST(req("/api/auth/otp", { login_ticket: "t", otp: "123456" }))).status).toBe(200);
    await Promise.all(afterFns.map((fn) => fn()));
    expect(agent.warmAgent).not.toHaveBeenCalled();
  });
  it("rejects a malformed body with 400 and a wrong code with 401", async () => {
    const { POST } = await import("@/app/api/auth/otp/route");
    expect((await POST(req("/api/auth/otp", { otp: 1 }))).status).toBe(400);
    const { IdpError } = await import("@/lib/server/idp");
    idp.otp.mockRejectedValue(new IdpError(401));
    expect((await POST(req("/api/auth/otp", { login_ticket: "t", otp: "000000" }))).status).toBe(401);
  });
});

describe("/api/auth/realtime-token", () => {
  it("uses the staff cookie when asked as staff, else the customer cookie; 401 without one", async () => {
    const { GET } = await import("@/app/api/auth/realtime-token/route");
    session.customerFrom.mockResolvedValue(null);
    expect((await GET(req("/api/auth/realtime-token"))).status).toBe(401);
    session.staffFrom.mockResolvedValue({ token: "staff-tok", sub: "agent.ana", sid: "STAFF-1", name: "Ana", exp: 0 });
    idp.realtimeToken.mockResolvedValue({ token: "rt", expires_in: 900 });
    const res = await GET(req("/api/auth/realtime-token?as=staff"));
    expect(idp.realtimeToken).toHaveBeenCalledWith("staff-tok");
    expect(await res.json()).toEqual({ data: { token: "rt", expires_in: 900 } });
  });
});

describe("/api/auth/demo-users and debug-claims", () => {
  it("are 404 outside demo mode", async () => {
    process.env.DEMO_MODE = "0";
    const du = await import("@/app/api/auth/demo-users/route");
    const dc = await import("@/app/api/auth/debug-claims/route");
    expect((await du.GET(req("/api/auth/demo-users"))).status).toBe(404);
    expect((await dc.GET(req("/api/auth/debug-claims"))).status).toBe(404);
  });
  it("demo-users never lists staff, even when asked", async () => {
    idp.demoUsers.mockResolvedValue([
      { username: "ana.mx", demo_password: "p", otp: "1", lang: "es", role: "customer", display_name: "", scenarios: [] },
      { username: "agent.ana", demo_password: "s", otp: "", lang: "es", role: "agent", display_name: "Ana", scenarios: [] }]);
    const { GET } = await import("@/app/api/auth/demo-users/route");
    const customers = (await (await GET(req("/api/auth/demo-users"))).json()).data;
    const staff = (await (await GET(req("/api/auth/demo-users?role=agent"))).json()).data;
    expect(customers.map((u: { username: string }) => u.username)).toEqual(["ana.mx"]);
    expect(staff).toEqual([]);
  });
  it("debug-claims needs a staff session and returns the customer's verified claims", async () => {
    const { GET } = await import("@/app/api/auth/debug-claims/route");
    session.staffFrom.mockResolvedValue(null);
    expect((await GET(req("/api/auth/debug-claims"))).status).toBe(401);
    session.staffFrom.mockResolvedValue({ token: "s", sub: "agent.ana", sid: "STAFF-1", name: "Ana", exp: 0 });
    session.customerFrom.mockResolvedValue({ token: "c", sub: "CLI-A", sid: "S-1", lang: "es", scopes: ["inquiry:read"], exp: 1790000000 });
    expect((await (await GET(req("/api/auth/debug-claims"))).json()).data).toEqual(
      { sub: "CLI-A", sid: "S-1", lang: "es", scopes: ["inquiry:read"], exp: 1790000000 });
  });
});
