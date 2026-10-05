import "server-only";
import { NextResponse } from "next/server";
import type { z } from "zod";

export const ok = <T>(data: T, status = 200) => NextResponse.json({ data }, { status });
export const fail = (code: string, message: string, status: number) => NextResponse.json({ error: { code, message } }, { status });

export async function readJson<S extends z.ZodTypeAny>(req: Request, schema: S): Promise<z.infer<S> | NextResponse> {
  let raw: unknown;
  try { raw = await req.json(); } catch { return fail("bad_request", "Body must be JSON", 400); }
  const parsed = schema.safeParse(raw);
  return parsed.success ? parsed.data : fail("bad_request", parsed.error.issues[0]?.message ?? "Invalid body", 400);
}
