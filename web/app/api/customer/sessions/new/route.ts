import { after, type NextRequest } from "next/server";
import { warmAgent } from "@/lib/server/agentcore";
import { endCurrent } from "@/lib/server/conversations";
import { fail, ok } from "@/lib/server/http";
import { IdpError, idp } from "@/lib/server/idp";
import { verifier } from "@/lib/server/jwt";
import { CUSTOMER_COOKIE, customerFrom, e2eNewSession, setSessionCookie } from "@/lib/server/session";

/** The IdP re-issues the token with a new sid but the same expiry, so a new conversation never extends the login. */
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
      t = { ...r, sid: (await verifier().customer(r.access_token)).sid };  // verify the IdP's token, never trust it blindly
    }
  } catch (e) {
    if (e instanceof IdpError) return fail("session_expired", "Sign in again", e.httpStatus === 503 ? 503 : 401);
    throw e;
  }
  const sid = t.sid;
  const res = ok({ session_id: sid, lang: t.lang, expires_in: t.expires_in });
  setSessionCookie(res, CUSTOMER_COOKIE, t.access_token, t.expires_in);
  after(async () => { await warmAgent({ token: t.access_token, sid }); });
  return res;
}
