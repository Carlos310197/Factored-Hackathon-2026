import type { NextRequest } from "next/server";
import { getHandoff } from "@/lib/server/handoffs";
import { fail, ok } from "@/lib/server/http";
import { staffFrom } from "@/lib/server/session";
import { getSession } from "@/lib/server/sessions";

export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  if (!(await staffFrom(req))) return fail("unauthorized", "Staff sign-in required", 401);
  const { id } = await params;
  const packet = await getHandoff(id);
  if (!packet) return fail("not_found", "Not found", 404);
  const session = await getSession(packet.session_id);
  return ok({ packet, control: session?.control ?? "agent" });
}
