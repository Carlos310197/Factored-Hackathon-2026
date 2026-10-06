import "server-only";
import { z } from "zod";
import { env } from "./env";

export class IdpError extends Error {
  constructor(readonly status: number) { super(`identity service ${status}`); }
  get httpStatus() { return this.status === 400 || this.status === 422 ? 400 : this.status < 500 ? 401 : 503; }
}
const DemoUser = z.object({ username: z.string(), demo_password: z.string(), otp: z.string(), lang: z.enum(["es", "pt"]),
  role: z.enum(["customer", "agent"]), display_name: z.string(), scenarios: z.array(z.string()) });
export type DemoUser = z.infer<typeof DemoUser>;

async function call<S extends z.ZodTypeAny>(path: string, schema: S, init: RequestInit = {}): Promise<z.infer<S>> {
  let res: Response;
  try {
    res = await fetch(`${env().IDP_URL}${path}`, { ...init, headers: { "content-type": "application/json", ...init.headers },
      signal: AbortSignal.timeout(15_000), cache: "no-store" });
  } catch {
    throw new IdpError(503);
  }
  if (!res.ok) throw new IdpError(res.status);
  const parsed = await res.json().then((j: unknown) => schema.safeParse(j), () => null);
  if (!parsed?.success) throw new IdpError(502);
  return parsed.data;
}

// a failure is not cached: the IdP may be cold
let demoUsersOnce: Promise<DemoUser[]> | null = null;

export const idp = {
  login: (username: string, password: string) =>
    call("/auth/login", z.object({ login_ticket: z.string() }), { method: "POST", body: JSON.stringify({ username, password }) }),
  otp: (login_ticket: string, otp: string, short_ttl = false) =>
    call("/auth/otp", z.object({ access_token: z.string(), expires_in: z.number(), lang: z.enum(["es", "pt"]) }),
      { method: "POST", body: JSON.stringify({ login_ticket, otp, short_ttl }) }),
  staffLogin: (username: string, password: string) =>
    call("/auth/staff/login", z.object({ access_token: z.string(), expires_in: z.number(), name: z.string() }),
      { method: "POST", body: JSON.stringify({ username, password }) }),
  newSession: (bearer: string) =>
    call("/auth/session/new", z.object({ access_token: z.string(), expires_in: z.number(), lang: z.enum(["es", "pt"]) }),
      { method: "POST", headers: { authorization: `Bearer ${bearer}` } }),
  realtimeToken: (bearer: string) =>
    call("/auth/realtime-token", z.object({ token: z.string(), expires_in: z.number() }),
      { method: "POST", headers: { authorization: `Bearer ${bearer}` } }),
  demoUsers: () => (demoUsersOnce ??= call("/auth/demo-users", z.array(DemoUser)).catch((e) => { demoUsersOnce = null; throw e; })),
};
