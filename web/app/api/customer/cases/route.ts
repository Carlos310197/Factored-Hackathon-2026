import type { NextRequest } from "next/server";
import { listCustomerCases } from "@/lib/server/disputes";
import { fail, ok } from "@/lib/server/http";
import { customerFrom } from "@/lib/server/session";

export async function GET(req: NextRequest) {
  const customer = await customerFrom(req);
  if (!customer) return fail("unauthorized", "Sign-in required", 401);
  return ok(await listCustomerCases(customer.sub));  // the id comes only from the token
}
