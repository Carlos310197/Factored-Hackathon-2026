import { LoginForm } from "@/components/customer/LoginForm";

type Search = Promise<Record<string, string | undefined>>;

export default async function LoginPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  // only same-site paths: "//host" would be an open redirect
  const next = q.next?.startsWith("/") && !q.next.startsWith("//") ? q.next : "/chat";
  return <LoginForm next={next} embed={q.embed === "1"} prefillUser={q.user} shortTtl={q.short === "1"} auto={q.auto === "1"} />;
}
