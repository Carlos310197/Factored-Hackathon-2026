import { notFound, redirect } from "next/navigation";
import { DemoStage } from "@/components/demo/DemoStage";
import { demoMode } from "@/lib/server/env";
import { staffFromCookies } from "@/lib/server/session";

export default async function DemoPage() {
  const me = await staffFromCookies(); // reads cookies first: keeps the page dynamic at build
  if (!me) redirect("/login?staff=1&next=/demo");
  if (!demoMode()) notFound();
  return <DemoStage me={{ sub: me.sub, name: me.name }} />;
}
