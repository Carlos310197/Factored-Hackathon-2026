import type { NextRequest } from "next/server";
import { endCurrent } from "@/lib/server/conversations";
import { fail, ok } from "@/lib/server/http";
import { customerFrom } from "@/lib/server/session";

export async function POST(req: NextRequest) {
  const who = await customerFrom(req);
  if (!who) return fail("session_expired", "Sign in again", 401);
  await endCurrent(who);
  return ok({ ended: true });
}
