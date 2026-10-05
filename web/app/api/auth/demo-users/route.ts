import type { NextRequest } from "next/server";
import { demoMode } from "@/lib/server/env";
import { fail, ok } from "@/lib/server/http";
import { idp } from "@/lib/server/idp";

/** Customer demo identities only: staff credentials are never published (they go in the submission text). */
export async function GET(req: NextRequest) {
  if (!demoMode()) return fail("not_found", "Not found", 404);
  if (req.nextUrl.searchParams.get("role") === "agent") return ok([]);
  return ok((await idp.demoUsers()).filter((u) => u.role === "customer"));
}
