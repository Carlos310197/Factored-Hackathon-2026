import { redirect } from "next/navigation";
import { StaffSignOut } from "@/components/staff/StaffSignOut";
import { TraceList } from "@/components/trace/TraceList";
import { staffFromCookies } from "@/lib/server/session";
import { getSession } from "@/lib/server/sessions";

export default async function TracePage({ params }: { params: Promise<{ sid: string }> }) {
  const { sid } = await params;
  if (!(await staffFromCookies())) redirect(`/login?staff=1&next=${encodeURIComponent(`/trace/${sid}`)}`);
  const session = await getSession(sid).catch(() => undefined);
  return (
    <main className="font-staff min-h-dvh bg-c-canvas text-c-ink p-5 max-w-3xl mx-auto">
      <div className="flex items-center justify-between"><h1 className="text-lg font-bold">Decision trace</h1><StaffSignOut className="text-c-muted hover:text-c-ink" /></div>
      <p className="text-xs text-c-muted mb-4">Session {sid}{session === undefined ? " · session details unavailable" : session ? ` · customer ${session.customer_id} · ${session.language === "es" ? "Spanish" : "Portuguese"}` : " · unknown session"}</p>
      <TraceList sid={sid} mode="page" />
    </main>
  );
}
