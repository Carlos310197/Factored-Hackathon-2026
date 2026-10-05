import type { NextRequest } from "next/server";
import { z } from "zod";
import { fail, ok, readJson } from "@/lib/server/http";
import { IdpError, idp } from "@/lib/server/idp";
import { STAFF_COOKIE, setSessionCookie } from "@/lib/server/session";

const Body = z.object({ username: z.string().min(1).max(64), password: z.string().min(1).max(128) });

export async function POST(req: NextRequest) {
  const body = await readJson(req, Body);
  if (body instanceof Response) return body;
  try {
    const t = await idp.staffLogin(body.username, body.password);
    const res = ok({ name: t.name });
    setSessionCookie(res, STAFF_COOKIE, t.access_token, t.expires_in);
    return res;
  } catch (e) {
    if (e instanceof IdpError) return fail("login_failed", "Invalid staff credentials", e.httpStatus);
    throw e;
  }
}
