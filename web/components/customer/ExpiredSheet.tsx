"use client";
import { useRouter } from "next/navigation";
import type { Lang } from "@/lib/contract";
import { t } from "@/lib/i18n";

export function ExpiredSheet({ lang, embed }: { lang: Lang; embed: boolean }) {
  const router = useRouter();
  const d = t(lang);
  return (
    <div className="fixed inset-0 z-10 flex items-end justify-center bg-b-ink/40">
      <div role="dialog" aria-modal="true" aria-labelledby="exp-title" aria-describedby="exp-body"
        className="flex w-full max-w-md flex-col gap-3 rounded-t-card bg-b-surface p-6 pb-8">
        <span aria-hidden className="mx-auto h-1 w-10 rounded-full bg-b-line" />
        <h2 id="exp-title" className="text-xl font-extrabold">{d.expiredTitle}</h2>
        <p id="exp-body" className="text-sm text-b-muted">{d.expiredBody}</p>
        <button type="button" autoFocus onClick={() => router.replace(`/login?next=/chat${embed ? "&embed=1" : ""}`)}
          className="min-h-12 w-full rounded-full bg-b-leaf text-base font-bold text-b-surface transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-cobalt">{d.signInAgain}</button>
      </div>
    </div>
  );
}
