import { createRemoteJWKSet, jwtVerify, type JWTVerifyGetKey } from "jose";
import { channelAllowed, segmentsOf } from "./rules";

export interface RealtimeClaims { sub: string; sid: string; role: "customer" | "agent" }
export interface AuthorizerEvent {
  authorizationToken: string;
  requestContext?: { operation?: string; channel?: string; channelNamespaceName?: string };
}
export interface AuthorizerResult { isAuthorized: boolean; handlerContext?: Record<string, string>; ttlOverride?: number }

export async function verifyRealtime(token: string, getKey: JWTVerifyGetKey, issuer: string): Promise<RealtimeClaims | null> {
  try {
    const { payload } = await jwtVerify(token, getKey, { issuer, audience: "realtime", algorithms: ["RS256"] });
    const { sub, sid, role } = payload as Record<string, unknown>;
    if (typeof sub !== "string" || typeof sid !== "string" || (role !== "customer" && role !== "agent")) return null;
    return { sub, sid, role };
  } catch {
    return null;
  }
}

export async function decide(event: AuthorizerEvent, getKey: JWTVerifyGetKey, issuer: string): Promise<AuthorizerResult> {
  const claims = await verifyRealtime(event.authorizationToken ?? "", getKey, issuer);
  if (!claims) return { isAuthorized: false };
  const channel = event.requestContext?.channel;
  if (channel && !channelAllowed(segmentsOf(channel), claims)) return { isAuthorized: false };
  // ttlOverride 0: decisions depend on the channel, so they must never be cached per token.
  return { isAuthorized: true, handlerContext: { role: claims.role, sid: claims.sid }, ttlOverride: 0 };
}

let jwks: JWTVerifyGetKey | undefined;

export const handler = async (event: AuthorizerEvent): Promise<AuthorizerResult> => {
  jwks ??= createRemoteJWKSet(new URL(process.env.IDP_JWKS_URL as string), { cacheMaxAge: 600_000 });
  return decide(event, jwks, process.env.IDP_ISSUER as string);
};
