import type { NextRequest } from "next/server";
import { z } from "zod";
import { fail, ok, readJson } from "@/lib/server/http";
import { IdpError, idp } from "@/lib/server/idp";
import { CUSTOMER_COOKIE, setSessionCookie } from "@/lib/server/session";

const Body = z.object({ login_ticket: z.string().min(1), otp: z.string().min(1).max(12), short_ttl: z.boolean().optional() });

export async function POST(req: NextRequest) {
  const body = await readJson(req, Body);
  if (body instanceof Response) return body;
  try {
    const t = await idp.otp(body.login_ticket, body.otp, body.short_ttl ?? false);
    const res = ok({ lang: t.lang, expires_in: t.expires_in });
    setSessionCookie(res, CUSTOMER_COOKIE, t.access_token, t.expires_in);
    return res;
  } catch (e) {
    if (e instanceof IdpError) return fail("otp_failed", "Invalid or expired code", e.httpStatus);
    throw e;
  }
}
