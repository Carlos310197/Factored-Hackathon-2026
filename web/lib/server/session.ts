import "server-only";
import { cookies } from "next/headers";
import type { NextRequest, NextResponse } from "next/server";
import { AuthFailure, verifier, type CustomerSession, type StaffSession } from "./jwt";

export const CUSTOMER_COOKIE = "cust_session";
export const STAFF_COOKIE = "staff_session";

async function safe<T>(fn: () => Promise<T>): Promise<T | null> {
  try { return await fn(); } catch (e) { if (e instanceof AuthFailure) return null; throw e; }
}

export async function customerFrom(req: NextRequest): Promise<CustomerSession | null> {
  const tok = req.cookies.get(CUSTOMER_COOKIE)?.value;
  return tok ? safe(() => verifier().customer(tok)) : null;
}
export async function staffFrom(req: NextRequest): Promise<StaffSession | null> {
  const tok = req.cookies.get(STAFF_COOKIE)?.value;
  return tok ? safe(() => verifier().staff(tok)) : null;
}
export async function customerFromCookies(): Promise<CustomerSession | null> {
  const tok = (await cookies()).get(CUSTOMER_COOKIE)?.value;
  return tok ? safe(() => verifier().customer(tok)) : null;
}
export async function staffFromCookies(): Promise<StaffSession | null> {
  const tok = (await cookies()).get(STAFF_COOKIE)?.value;
  return tok ? safe(() => verifier().staff(tok)) : null;
}

export function setSessionCookie(res: NextResponse, name: string, token: string, maxAge: number) {
  res.cookies.set(name, token, { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge });
}
export function clearSessionCookie(res: NextResponse, name: string) {
  res.cookies.set(name, "", { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 });
}
