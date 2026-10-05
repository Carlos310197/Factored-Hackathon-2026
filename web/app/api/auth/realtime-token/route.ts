import type { NextRequest } from "next/server";
import { fail, ok } from "@/lib/server/http";
import { IdpError, idp } from "@/lib/server/idp";
import { customerFrom, staffFrom } from "@/lib/server/session";

export async function GET(req: NextRequest) {
  const asStaff = req.nextUrl.searchParams.get("as") === "staff";
  const who = asStaff ? await staffFrom(req) : await customerFrom(req);
  if (!who) return fail("session_expired", "Sign in again", 401);
  try {
    return ok(await idp.realtimeToken(who.token));
  } catch (e) {
    if (e instanceof IdpError) {
      return e.status === 401 ? fail("session_expired", "Sign in again", 401)
        : fail("realtime_unavailable", "Realtime token unavailable", e.httpStatus);
    }
    throw e;
  }
}
