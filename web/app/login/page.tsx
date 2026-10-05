import { LoginForm } from "@/components/customer/LoginForm";
import { StaffLogin } from "@/components/staff/StaffLogin";
import { safeNext } from "@/lib/safe-next";
import { demoMode } from "@/lib/server/env";
import { idp } from "@/lib/server/idp";

/** Demo identities rendered into the page so the form is filled on first paint. A cold IdP gets 1.5 s, then the form fetches them itself. */
async function demoCustomers() {
  if (!demoMode()) return null;
  const users = idp.demoUsers().then((us) => us.filter((u) => u.role === "customer"), () => null);
  return Promise.race([users, new Promise<null>((r) => setTimeout(() => r(null), 1500))]);
}

type Search = Promise<Record<string, string | undefined>>;

export default async function LoginPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  if (q.staff === "1") return <StaffLogin next={safeNext(q.next, "/agent")} />;
  const next = safeNext(q.next);
  return <LoginForm next={next} embed={q.embed === "1"} initialUsers={await demoCustomers()} prefillUser={q.user} shortTtl={q.short === "1"} auto={q.auto === "1"} />;
}
