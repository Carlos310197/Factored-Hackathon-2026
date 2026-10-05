import "server-only";
import { cookies } from "next/headers";
import type { NextRequest, NextResponse } from "next/server";
import { AuthFailure, verifier, type CustomerSession, type StaffSession } from "./jwt";

// SECURITY: this accepts forged unsigned cookies. E2E_MOCK must NEVER be set in any deployment (the demo
// deployment runs with DEMO_MODE=1, so DEMO_MODE alone must not enable it). Local Playwright webServer only.
// Fargate always sets ECS_CONTAINER_METADATA_URI_V4, so the forged path is also refused on any ECS task.
const e2e = () => process.env.E2E_MOCK === "1" && process.env.DEMO_MODE === "1" && !process.env.ECS_CONTAINER_METADATA_URI_V4;
function e2eCustomer(tok: string): CustomerSession | null {
  if (!e2e() || !tok.startsWith("e2e.customer.")) return null;
  const [, , sub, sid, lang] = tok.split(".");
  return { token: tok, sub, sid, lang: lang === "pt" ? "pt" : "es", scopes: ["dispute:create", "inquiry:read"], exp: Math.floor(Date.now() / 1000) + 900 };
}
function e2eStaff(tok: string): StaffSession | null {
  if (!e2e() || !tok.startsWith("e2e.staff.")) return null;
  const rest = tok.slice("e2e.staff.".length);
  const sub = rest.split(".").slice(0, 2).join(".");
  return { token: tok, sub, sid: "STAFF-e2e", name: rest.slice(sub.length + 1), exp: Math.floor(Date.now() / 1000) + 900 };
}

export const CUSTOMER_COOKIE = "cust_session";
export const STAFF_COOKIE = "staff_session";

async function safe<T>(fn: () => Promise<T>): Promise<T | null> {
  try { return await fn(); } catch (e) { if (e instanceof AuthFailure) return null; throw e; }
}

export async function customerFrom(req: NextRequest): Promise<CustomerSession | null> {
  const tok = req.cookies.get(CUSTOMER_COOKIE)?.value;
  return tok ? e2eCustomer(tok) ?? safe(() => verifier().customer(tok)) : null;
}
export async function staffFrom(req: NextRequest): Promise<StaffSession | null> {
  const tok = req.cookies.get(STAFF_COOKIE)?.value;
  return tok ? e2eStaff(tok) ?? safe(() => verifier().staff(tok)) : null;
}
export async function customerFromCookies(): Promise<CustomerSession | null> {
  const tok = (await cookies()).get(CUSTOMER_COOKIE)?.value;
  return tok ? e2eCustomer(tok) ?? safe(() => verifier().customer(tok)) : null;
}
export async function staffFromCookies(): Promise<StaffSession | null> {
  const tok = (await cookies()).get(STAFF_COOKIE)?.value;
  return tok ? e2eStaff(tok) ?? safe(() => verifier().staff(tok)) : null;
}

/** Secure cookies need HTTPS; the plain-HTTP ECS deployment sets COOKIE_SECURE=0. Default: secure in production. */
const cookieSecure = () => (process.env.COOKIE_SECURE ?? (process.env.NODE_ENV === "production" ? "1" : "0")) === "1";

export function setSessionCookie(res: NextResponse, name: string, token: string, maxAge: number) {
  res.cookies.set(name, token, { httpOnly: true, secure: cookieSecure(), sameSite: "lax", path: "/", maxAge });
}
export function clearSessionCookie(res: NextResponse, name: string) {
  res.cookies.set(name, "", { httpOnly: true, secure: cookieSecure(), sameSite: "lax", path: "/", maxAge: 0 });
}
