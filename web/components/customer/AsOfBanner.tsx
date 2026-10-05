import type { Lang } from "@/lib/contract";
import { fmtDate } from "@/lib/format";
import { t } from "@/lib/i18n";

export function AsOfBanner({ date, lang }: { date: string | null; lang: Lang }) {
  if (!date) return null;
  return <p className="bg-b-sun-tint px-4 py-1.5 text-center text-xs font-semibold text-b-ink">{t(lang).asOf(fmtDate(date, lang))}</p>;
}
