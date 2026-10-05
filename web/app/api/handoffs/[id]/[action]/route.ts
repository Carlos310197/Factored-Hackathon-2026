import type { NextRequest } from "next/server";
import { z } from "zod";
import { ResolutionCode } from "@/lib/contract";
import { ConflictError, NotFoundError } from "@/lib/server/ddb";
import { claim, resolve, returnToAssistant, takeover } from "@/lib/server/handoffs";
import { fail, ok, readJson } from "@/lib/server/http";
import { staffFrom } from "@/lib/server/session";

const ResolveBody = z.object({ code: ResolutionCode, note: z.string().max(500).default("") });

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string; action: string }> }) {
  const staff = await staffFrom(req);
  if (!staff) return fail("unauthorized", "Staff sign-in required", 401);
  const { id, action } = await params;
  try {
    switch (action) {
      case "claim": return ok(await claim(id, staff.sub));
      case "takeover": return ok(await takeover(id, staff.sub, staff.name));
      case "return": return ok(await returnToAssistant(id, staff.sub));
      case "resolve": {
        const body = await readJson(req, ResolveBody);
        if (body instanceof Response) return body;
        return ok(await resolve(id, staff.sub, body.code, body.note));
      }
      default: return fail("not_found", "Unknown action", 404);
    }
  } catch (e) {
    if (e instanceof ConflictError) return fail("conflict", "Someone else changed this case. Refresh and try again.", 409);
    if (e instanceof NotFoundError) return fail("not_found", "Not found", 404);
    throw e;
  }
}
