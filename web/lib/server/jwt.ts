import "server-only";
import { createRemoteJWKSet, errors, jwtVerify, type JWTVerifyGetKey } from "jose";
import { Lang } from "@/lib/contract";
import { env } from "./env";

export class AuthFailure extends Error {
  constructor(readonly reason: "expired" | "invalid") { super(reason); }
}
export interface CustomerSession { token: string; sub: string; sid: string; lang: Lang; scopes: string[]; exp: number }
export interface StaffSession { token: string; sub: string; sid: string; name: string; exp: number }

export function makeVerifier(getKey: JWTVerifyGetKey, cfg: { issuer: string; audience: string; staffAudience: string }) {
  async function verify(token: string, audience: string) {
    try {
      return (await jwtVerify(token, getKey, { issuer: cfg.issuer, audience, algorithms: ["RS256"] })).payload;
    } catch (e) {
      throw new AuthFailure(e instanceof errors.JWTExpired ? "expired" : "invalid");
    }
  }
  return {
    async customer(token: string): Promise<CustomerSession> {
      const p = await verify(token, cfg.audience);
      if (typeof p.sub !== "string" || typeof p.sid !== "string") throw new AuthFailure("invalid");
      return { token, sub: p.sub, sid: p.sid, lang: Lang.catch("es").parse(p.lang),
        scopes: String(p.scope ?? "").split(" ").filter(Boolean).sort(), exp: Number(p.exp) };
    },
    async staff(token: string): Promise<StaffSession> {
      const p = await verify(token, cfg.staffAudience);
      if (p.role !== "agent" || typeof p.sub !== "string" || typeof p.sid !== "string") throw new AuthFailure("invalid");
      return { token, sub: p.sub, sid: p.sid, name: typeof p.name === "string" ? p.name : p.sub, exp: Number(p.exp) };
    },
  };
}

let cached: ReturnType<typeof makeVerifier> | undefined;
export function verifier() {
  const e = env();
  cached ??= makeVerifier(createRemoteJWKSet(new URL(`${e.IDP_URL}/jwks.json`), { cacheMaxAge: 600_000 }),
    { issuer: e.IDP_ISSUER, audience: e.IDP_AUDIENCE, staffAudience: e.STAFF_AUDIENCE });
  return cached;
}
