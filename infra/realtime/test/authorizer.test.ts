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
  it("refuses an invalid token", async () => {
    expect((await decide({ authorizationToken: "x" }, jwks, ISS)).isAuthorized).toBe(false);
  });
});
