import type { NextRequest } from "next/server";
import { demoMode } from "@/lib/server/env";
import { fail, ok } from "@/lib/server/http";
import { customerFrom, staffFrom } from "@/lib/server/session";

export async function GET(req: NextRequest) {
  if (!demoMode()) return fail("not_found", "Not found", 404);
  if (!(await staffFrom(req))) return fail("unauthorized", "Staff sign-in required", 401);
  const c = await customerFrom(req);
  if (!c) return fail("no_customer", "No customer signed in on this browser", 404);
  return ok({ sub: c.sub, sid: c.sid, lang: c.lang, scopes: c.scopes, exp: c.exp });
}
