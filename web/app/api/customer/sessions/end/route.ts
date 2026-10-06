import type { NextRequest } from "next/server";
import { endCurrent } from "@/lib/server/conversations";
import { fail, ok } from "@/lib/server/http";
import { customerFrom } from "@/lib/server/session";

/** Ends the token's conversation; after this, /api/chat answers 409 session_ended for it. */
export async function POST(req: NextRequest) {
  const who = await customerFrom(req);
  if (!who) return fail("session_expired", "Sign in again", 401);
  await endCurrent(who);
  return ok({ ended: true });
}
