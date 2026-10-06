import type { NextRequest } from "next/server";
import { fail, ok } from "@/lib/server/http";
import { customerFrom } from "@/lib/server/session";
import { listCustomerSessions } from "@/lib/server/sessions";

/** The customer id comes only from the token. */
export async function GET(req: NextRequest) {
  const who = await customerFrom(req);
  if (!who) return fail("session_expired", "Sign in again", 401);
  const rows = (await listCustomerSessions(who.sub)).map((r) => ({ ...r, current: r.session_id === who.sid }));
  // the agent creates the session item on the first turn, so a brand-new conversation is not stored yet
  if (!rows.some((r) => r.current)) {
    rows.unshift({ session_id: who.sid, created_at: new Date().toISOString(), language: who.lang, ended: false, preview: null, current: true });
  }
  return ok(rows);
}
