import type { NextRequest } from "next/server";
import { z } from "zod";
import { fail, ok, readJson } from "@/lib/server/http";
import { IdpError, idp } from "@/lib/server/idp";

const Body = z.object({ username: z.string().min(1).max(64), password: z.string().min(1).max(128) });

export async function POST(req: NextRequest) {
  const body = await readJson(req, Body);
  if (body instanceof Response) return body;
  try {
    return ok(await idp.login(body.username, body.password));
  } catch (e) {
    if (e instanceof IdpError) return fail("login_failed", "Invalid credentials", e.httpStatus);
    throw e;
  }
}
