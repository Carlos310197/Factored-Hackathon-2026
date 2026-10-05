import { redirect } from "next/navigation";
import { TraceList } from "@/components/trace/TraceList";
import { staffFromCookies } from "@/lib/server/session";
import { getSession } from "@/lib/server/sessions";

export default async function TracePage({ params }: { params: Promise<{ sid: string }> }) {
  const { sid } = await params;
  if (!(await staffFromCookies())) redirect(`/login?staff=1&next=${encodeURIComponent(`/trace/${sid}`)}`);
  const session = await getSession(sid);
  return (
    <main className="font-staff min-h-dvh bg-c-canvas text-c-ink p-5 max-w-3xl mx-auto">
      <h1 className="text-lg font-bold">Decision trace</h1>
      <p className="text-xs text-c-muted mb-4">Session {sid}{session ? ` · customer ${session.customer_id} · ${session.language === "es" ? "Spanish" : "Portuguese"}` : ""}</p>
      <TraceList sid={sid} mode="page" />
    </main>
  );
}
