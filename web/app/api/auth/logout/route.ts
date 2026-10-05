import type { NextRequest } from "next/server";
import { z } from "zod";
import { ok, readJson } from "@/lib/server/http";
import { CUSTOMER_COOKIE, STAFF_COOKIE, clearSessionCookie } from "@/lib/server/session";

export async function POST(req: NextRequest) {
  const body = await readJson(req, z.object({ who: z.enum(["customer", "staff"]) }));
  if (body instanceof Response) return body;
  const res = ok({ signed_out: body.who });
  clearSessionCookie(res, body.who === "staff" ? STAFF_COOKIE : CUSTOMER_COOKIE);
  return res;
}
