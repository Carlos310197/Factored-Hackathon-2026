import type { Lang } from "@/lib/contract";
import { fmtDate } from "@/lib/format";
import { t } from "@/lib/i18n";

export function AsOfBanner({ date, lang }: { date: string | null; lang: Lang }) {
  // ponytail: the row is always there so the transcript never jumps when the first reply brings the date
  if (!date) return <p aria-hidden="true" className="px-4 py-1.5 text-xs">&nbsp;</p>;
  return <p className="bg-b-sun-tint px-4 py-1.5 text-center text-xs font-semibold text-b-ink motion-safe:animate-[fade-in_200ms_ease-out]">{t(lang).asOf(fmtDate(date, lang))}</p>;
}
