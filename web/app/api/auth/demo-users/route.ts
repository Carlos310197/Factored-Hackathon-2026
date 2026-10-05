import type { NextRequest } from "next/server";
import { demoMode } from "@/lib/server/env";
import { fail, ok } from "@/lib/server/http";
import { idp } from "@/lib/server/idp";

export async function GET(req: NextRequest) {
  if (!demoMode()) return fail("not_found", "Not found", 404);
  const role = req.nextUrl.searchParams.get("role") === "agent" ? "agent" : "customer";
  return ok((await idp.demoUsers()).filter((u) => u.role === role));
}
