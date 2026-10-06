import { redirect } from "next/navigation";
import { ChatScreen } from "@/components/customer/ChatScreen";
import { customerFromCookies } from "@/lib/server/session";

export default async function ChatPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const embed = (await searchParams).embed === "1";
  const who = await customerFromCookies();
  if (!who) redirect(`/login?next=/chat${embed ? "&embed=1" : ""}`);
  return <ChatScreen key={who.sid} sid={who.sid} lang={who.lang} embed={embed} />;
}
