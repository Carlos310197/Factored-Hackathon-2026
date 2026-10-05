import { SignJWT, exportJWK, generateKeyPair, createLocalJWKSet } from "jose";
import { beforeAll, describe, expect, it } from "vitest";
import { channelAllowed } from "../authorizer/rules";
import { decide, verifyRealtime } from "../authorizer/index";
import { CASES } from "./rules.cases";

const ISS = "http://idp.test";
let jwks: ReturnType<typeof createLocalJWKSet>;
let sign: (claims: Record<string, unknown>, aud?: string, exp?: string) => Promise<string>;

beforeAll(async () => {
  const { privateKey, publicKey } = await generateKeyPair("RS256");
  const jwk = { ...(await exportJWK(publicKey)), kid: "k1", alg: "RS256", use: "sig" };
  jwks = createLocalJWKSet({ keys: [jwk] });
  sign = (claims, aud = "realtime", exp = "5m") =>
    new SignJWT(claims).setProtectedHeader({ alg: "RS256", kid: "k1" }).setIssuer(ISS).setAudience(aud)
      .setIssuedAt().setExpirationTime(exp).sign(privateKey);
});

describe("channelAllowed", () => {
  it.each(CASES)("%s", (_n, segments, c, ok) => expect(channelAllowed(segments, c)).toBe(ok));
});

describe("verifyRealtime", () => {
  it("accepts a realtime token", async () => {
    const t = await sign({ sub: "CLI-A", sid: "S-1", role: "customer" });
    expect(await verifyRealtime(t, jwks, ISS)).toEqual({ sub: "CLI-A", sid: "S-1", role: "customer" });
  });
  it("rejects an access token (wrong audience), an expired token and garbage", async () => {
    expect(await verifyRealtime(await sign({ sub: "CLI-A", sid: "S-1", role: "customer" }, "bankagent"), jwks, ISS)).toBeNull();
    expect(await verifyRealtime(await sign({ sub: "CLI-A", sid: "S-1", role: "customer" }, "realtime", "-1m"), jwks, ISS)).toBeNull();
    expect(await verifyRealtime("nope", jwks, ISS)).toBeNull();
  });
  it("rejects a wrong issuer, an HS256 token and an empty sid", async () => {
    const t = await sign({ sub: "CLI-A", sid: "S-1", role: "customer" });
    expect(await verifyRealtime(t, jwks, "http://other.test")).toBeNull();
    const hs = await new SignJWT({ sub: "CLI-A", sid: "S-1", role: "customer" }).setProtectedHeader({ alg: "HS256", kid: "k1" })
      .setIssuer(ISS).setAudience("realtime").setExpirationTime("5m").sign(new TextEncoder().encode("secret-secret-secret-secret-32b"));
    expect(await verifyRealtime(hs, jwks, ISS)).toBeNull();
    expect(await verifyRealtime(await sign({ sub: "CLI-A", sid: "", role: "customer" }), jwks, ISS)).toBeNull();
  });
  it("rejects tokens without role or sid", async () => {
    expect(await verifyRealtime(await sign({ sub: "CLI-A", sid: "S-1" }), jwks, ISS)).toBeNull();
  });
});

describe("decide", () => {
  it("authorizes connect without a channel and passes role+sid as handlerContext, no caching", async () => {
    const t = await sign({ sub: "CLI-A", sid: "S-1", role: "customer" });
    const r = await decide({ authorizationToken: t, requestContext: { operation: "EVENT_CONNECT" } }, jwks, ISS);
    expect(r).toEqual({ isAuthorized: true, handlerContext: { role: "customer", sid: "S-1" }, ttlOverride: 0 });
  });
  it("refuses a customer subscribing to another session when the channel is known", async () => {
    const t = await sign({ sub: "CLI-A", sid: "S-1", role: "customer" });
    const r = await decide({ authorizationToken: t, requestContext: { operation: "EVENT_SUBSCRIBE", channel: "/session/S-2" } }, jwks, ISS);
    expect(r.isAuthorized).toBe(false);
  });
  it("allows a customer's own channel and an agent's queue", async () => {
    const c = await sign({ sub: "CLI-A", sid: "S-1", role: "customer" });
    expect((await decide({ authorizationToken: c, requestContext: { operation: "EVENT_SUBSCRIBE", channel: "/session/S-1" } }, jwks, ISS)).isAuthorized).toBe(true);
    const a = await sign({ sub: "STAFF-1", sid: "STAFF-1", role: "agent" });
    expect((await decide({ authorizationToken: a, requestContext: { operation: "EVENT_SUBSCRIBE", channel: "/queue/all" } }, jwks, ISS)).isAuthorized).toBe(true);
  });
  it("refuses publish even for a valid agent token", async () => {
    const a = await sign({ sub: "STAFF-1", sid: "STAFF-1", role: "agent" });
    expect((await decide({ authorizationToken: a, requestContext: { operation: "EVENT_PUBLISH", channel: "/queue/all" } }, jwks, ISS)).isAuthorized).toBe(false);
  });
  it("refuses a malformed channel with an empty segment", async () => {
    const a = await sign({ sub: "STAFF-1", sid: "STAFF-1", role: "agent" });
    expect((await decide({ authorizationToken: a, requestContext: { operation: "EVENT_SUBSCRIBE", channel: "/session//S-1" } }, jwks, ISS)).isAuthorized).toBe(false);
  });
  it("refuses an invalid token", async () => {
    expect((await decide({ authorizationToken: "x" }, jwks, ISS)).isAuthorized).toBe(false);
  });
});
