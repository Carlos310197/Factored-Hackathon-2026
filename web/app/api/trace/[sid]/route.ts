import type { NextRequest } from "next/server";
import { fail, ok } from "@/lib/server/http";
import { listMessages } from "@/lib/server/messages";
import { listRecords } from "@/lib/server/records";
import { staffFrom } from "@/lib/server/session";
import { buildTrace } from "@/lib/trace/viewModel";

export async function GET(req: NextRequest, { params }: { params: Promise<{ sid: string }> }) {
  if (!(await staffFrom(req))) return fail("unauthorized", "Staff sign-in required", 401);
  const { sid } = await params;
  const turn = req.nextUrl.searchParams.get("turn") ?? undefined;
  const [records, messages] = await Promise.all([listRecords(sid, turn), listMessages(sid)]);
  return ok(buildTrace(records, messages));
}
