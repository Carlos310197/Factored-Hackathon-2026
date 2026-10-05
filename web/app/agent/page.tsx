import { redirect } from "next/navigation";
import { ConsoleWithTabs } from "@/components/staff/ConsoleWithTabs";
import { staffFromCookies } from "@/lib/server/session";

export default async function AgentPage() {
  const me = await staffFromCookies();
  if (!me) redirect("/login?staff=1&next=/agent");
  return <ConsoleWithTabs me={{ sub: me.sub, name: me.name }} />;
}
