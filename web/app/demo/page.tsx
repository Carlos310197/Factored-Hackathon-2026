import { notFound, redirect } from "next/navigation";
import { DemoStage } from "@/components/demo/DemoStage";
import { demoMode } from "@/lib/server/env";
import { staffFromCookies } from "@/lib/server/session";

export default async function DemoPage() {
  if (!(await staffFromCookies())) redirect("/login?staff=1&next=/demo"); // reads cookies first: keeps the page dynamic at build
  if (!demoMode()) notFound();
  return <DemoStage />;
}
