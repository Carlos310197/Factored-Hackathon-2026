import type { NextRequest } from "next/server";
import { NotFoundError } from "@/lib/server/ddb";
import { fail, ok } from "@/lib/server/http";
import { customerFrom } from "@/lib/server/session";
import { hideSession } from "@/lib/server/sessions";

type Ctx = { params: Promise<{ sid: string }> };

export async function POST(req: NextRequest, { params }: Ctx) {
  const who = await customerFrom(req);
  if (!who) return fail("session_expired", "Sign in again", 401);
  const { sid } = await params;
  if (sid === who.sid) return fail("current_session", "End the conversation before hiding it", 409);
  try {
    await hideSession(sid, who.sub);
  } catch (e) {
    if (e instanceof NotFoundError) return fail("not_found", "Not found", 404);  // same answer for someone else's session
    throw e;
  }
  return ok({ hidden: true });
}
