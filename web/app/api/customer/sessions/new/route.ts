import { after, type NextRequest } from "next/server";
import { warmAgent } from "@/lib/server/agentcore";
import { endCurrent } from "@/lib/server/conversations";
import { fail, ok } from "@/lib/server/http";
import { IdpError, idp } from "@/lib/server/idp";
import { verifier } from "@/lib/server/jwt";
import { CUSTOMER_COOKIE, customerFrom, e2eNewSession, setSessionCookie } from "@/lib/server/session";

/** Ends the current conversation and starts a new one: the IdP re-issues the customer's token with a new session id
 * (same customer, scopes and expiry), so the login itself is never extended. */
export async function POST(req: NextRequest) {
  const who = await customerFrom(req);
  if (!who) return fail("session_expired", "Sign in again", 401);
  await endCurrent(who);
  let t: { access_token: string; expires_in: number; lang: "es" | "pt"; sid: string };
  try {
    const forged = e2eNewSession(who);
    if (forged) t = forged;
    else {
      const r = await idp.newSession(who.token);
      t = { ...r, sid: (await verifier().customer(r.access_token)).sid }; // the IdP's own token: verify, never trust blindly
    }
  } catch (e) {
    if (e instanceof IdpError) return fail("session_expired", "Sign in again", e.httpStatus === 503 ? 503 : 401);
    throw e;
  }
  const sid = t.sid;
  const res = ok({ session_id: sid, lang: t.lang, expires_in: t.expires_in });
  setSessionCookie(res, CUSTOMER_COOKIE, t.access_token, t.expires_in);
  after(async () => { await warmAgent({ token: t.access_token, sid }); }); // same warm-up as a fresh login
  return res;
}
