import { beforeAll, describe, expect, it } from "vitest";
import { AuthFailure, makeVerifier } from "@/lib/server/jwt";
import { ISS, testKeys } from "../helpers/keys";

let k: Awaited<ReturnType<typeof testKeys>>;
let v: ReturnType<typeof makeVerifier>;
beforeAll(async () => {
  k = await testKeys();
  v = makeVerifier(k.getKey, { issuer: ISS, audience: "bankagent", staffAudience: "bankagent-staff" });
});

describe("verifier", () => {
  it("reads a customer session only from verified claims", async () => {
    const tok = await k.sign({ sub: "CLI-A", sid: "S-1", lang: "pt", scope: "dispute:create inquiry:read", role: "customer" }, "bankagent");
    const s = await v.customer(tok);
    expect(s).toMatchObject({ sub: "CLI-A", sid: "S-1", lang: "pt", scopes: ["dispute:create", "inquiry:read"], token: tok });
  });
  it("rejects a staff token as a customer and a customer token as staff", async () => {
    const staff = await k.sign({ sub: "agent.ana", sid: "STAFF-1", role: "agent", name: "Ana R.", scope: "handoff:work" }, "bankagent-staff");
    const cust = await k.sign({ sub: "CLI-A", sid: "S-1", lang: "es", scope: "inquiry:read", role: "customer" }, "bankagent");
    await expect(v.customer(staff)).rejects.toBeInstanceOf(AuthFailure);
    await expect(v.staff(cust)).rejects.toBeInstanceOf(AuthFailure);
    expect((await v.staff(staff)).name).toBe("Ana R.");
  });
  it("reports expiry distinctly", async () => {
    const tok = await k.sign({ sub: "CLI-A", sid: "S-1", lang: "es", scope: "", role: "customer" }, "bankagent", "-1m");
    await expect(v.customer(tok)).rejects.toMatchObject({ reason: "expired" });
  });
  it("rejects a staff-audience token without role agent", async () => {
    const tok = await k.sign({ sub: "x", sid: "STAFF-1", role: "customer", scope: "handoff:work" }, "bankagent-staff");
    await expect(v.staff(tok)).rejects.toMatchObject({ reason: "invalid" });
  });
});
