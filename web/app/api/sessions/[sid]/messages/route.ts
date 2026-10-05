import type { NextRequest } from "next/server";
import { z } from "zod";
import { fail, ok, readJson } from "@/lib/server/http";
import { appendMessage, listMessages } from "@/lib/server/messages";
import { customerFrom, staffFrom } from "@/lib/server/session";
import { getSession } from "@/lib/server/sessions";

type Ctx = { params: Promise<{ sid: string }> };

export async function GET(req: NextRequest, { params }: Ctx) {
  const { sid } = await params;
  const [customer, staff] = [await customerFrom(req), await staffFrom(req)];
  const session = await getSession(sid);
  const ownerOk = customer && session && customer.sid === sid && session.customer_id === customer.sub;
  if (!session || (!ownerOk && !staff)) return fail("not_found", "Not found", 404);  // same answer as a missing session
  const after = req.nextUrl.searchParams.get("after") ?? undefined;
  return ok(await listMessages(sid, after));
}

export async function POST(req: NextRequest, { params }: Ctx) {
  const { sid } = await params;
  const staff = await staffFrom(req);
  if (!staff) return fail("unauthorized", "Staff sign-in required", 401);
  const body = await readJson(req, z.object({ text: z.string().trim().min(1).max(2000) }));
  if (body instanceof Response) return body;
  const session = await getSession(sid);
  if (!session) return fail("not_found", "Not found", 404);
  if (session.control !== `human:${staff.sub}`) return fail("conflict", "Take over the conversation first", 409);
  return ok(await appendMessage(sid, { role: "agent", text: body.text, author: staff.name }), 201);
}
