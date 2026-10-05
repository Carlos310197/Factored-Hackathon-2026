import { LoginForm } from "@/components/customer/LoginForm";
import { StaffLogin } from "@/components/staff/StaffLogin";
import { safeNext } from "@/lib/safe-next";

type Search = Promise<Record<string, string | undefined>>;

export default async function LoginPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  if (q.staff === "1") return <StaffLogin next={safeNext(q.next, "/agent")} />;
  const next = safeNext(q.next);
  return <LoginForm next={next} embed={q.embed === "1"} prefillUser={q.user} shortTtl={q.short === "1"} auto={q.auto === "1"} />;
}
