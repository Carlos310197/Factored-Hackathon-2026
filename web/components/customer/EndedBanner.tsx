"use client";
import { useState } from "react";
import type { Lang } from "@/lib/contract";
import { t } from "@/lib/i18n";

export function EndedBanner({ lang, onNew, onSignOut }: { lang: Lang; onNew: () => Promise<boolean>; onSignOut: () => void }) {
  const d = t(lang);
  const [failed, setFailed] = useState(false);
  return (
    <section aria-labelledby="ended-title" className="mx-3 mb-3 flex shrink-0 flex-col gap-2 rounded-card bg-b-fog p-4 motion-safe:animate-[fade-in_220ms_ease-out]">
      <h2 id="ended-title" className="text-base font-extrabold">{d.endedTitle}</h2>
      <p className="text-sm text-b-muted">{failed ? d.actionFailed : d.endedBody}</p>
      <span className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void onNew().then((ok) => setFailed(!ok))}
          className="min-h-11 rounded-full bg-b-leaf px-4 text-sm font-bold text-b-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-cobalt">{d.newConversation}</button>
        <button type="button" onClick={onSignOut}
          className="min-h-11 rounded-full border-[1.5px] border-b-ink bg-b-surface px-4 text-sm font-bold text-b-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-cobalt">{d.signOut}</button>
      </span>
    </section>
  );
}
