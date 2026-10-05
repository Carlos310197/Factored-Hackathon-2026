import { redirect } from "next/navigation";
import { ConsoleWithTabs } from "@/components/staff/ConsoleWithTabs";
import { staffFromCookies } from "@/lib/server/session";

export default async function AgentCasePage({ params }: { params: Promise<{ handoffId: string }> }) {
  const { handoffId } = await params;
  const me = await staffFromCookies();
  if (!me) redirect(`/login?staff=1&next=${encodeURIComponent(`/agent/${handoffId}`)}`);
  return <ConsoleWithTabs me={{ sub: me.sub, name: me.name }} initialId={handoffId} />;
}
