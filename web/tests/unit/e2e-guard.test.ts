import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server/jwt", async (orig) => ({ ...(await orig<typeof import("@/lib/server/jwt")>()),
  verifier: () => ({ customer: async () => { throw new (await import("@/lib/server/jwt")).AuthFailure("invalid"); },
    staff: async () => { throw new (await import("@/lib/server/jwt")).AuthFailure("invalid"); } }) }));

const req = (cookie: string) => new NextRequest("http://localhost/", { headers: { cookie } });
afterEach(() => { delete process.env.E2E_MOCK; delete process.env.DEMO_MODE; });

describe("E2E cookies", () => {
  it("are ignored unless E2E_MOCK=1 and DEMO_MODE=1", async () => {
    const { customerFrom, staffFrom } = await import("@/lib/server/session");
    expect(await customerFrom(req("cust_session=e2e.customer.CLI-A.S-1.es"))).toBeNull();
    process.env.E2E_MOCK = "1";
    expect(await customerFrom(req("cust_session=e2e.customer.CLI-A.S-1.es"))).toBeNull();
    process.env.DEMO_MODE = "1";
    expect(await customerFrom(req("cust_session=e2e.customer.CLI-A.S-1.es"))).toMatchObject({ sub: "CLI-A", sid: "S-1", lang: "es" });
    expect(await staffFrom(req("staff_session=e2e.staff.agent.ana.Ana R."))).toMatchObject({ sub: "agent.ana", name: "Ana R." });
  });
});
