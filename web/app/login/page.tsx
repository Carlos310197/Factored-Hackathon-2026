import { LoginForm } from "@/components/customer/LoginForm";
import { safeNext } from "@/lib/safe-next";

type Search = Promise<Record<string, string | undefined>>;

export default async function LoginPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const next = safeNext(q.next);
  return <LoginForm next={next} embed={q.embed === "1"} prefillUser={q.user} shortTtl={q.short === "1"} auto={q.auto === "1"} />;
}
