import type { NextRequest } from "next/server";
import type { HandoffStatus } from "@/lib/contract";
import { listHandoffs } from "@/lib/server/handoffs";
import { fail, ok } from "@/lib/server/http";
import { staffFrom } from "@/lib/server/session";

const FILTERS: Record<string, HandoffStatus[]> = {
  open: ["open"], mine: ["claimed", "in_takeover", "returned"], in_takeover: ["in_takeover"], resolved: ["resolved"],
};

export async function GET(req: NextRequest) {
  const staff = await staffFrom(req);
  if (!staff) return fail("unauthorized", "Staff sign-in required", 401);
  const filter = req.nextUrl.searchParams.get("filter") ?? "open";
  const statuses = FILTERS[filter];
  if (!statuses) return fail("bad_request", "Unknown filter", 400);
  const rows = await listHandoffs(statuses);
  return ok(filter === "mine" ? rows.filter((r) => r.claimed_by === staff.sub) : rows);
}
