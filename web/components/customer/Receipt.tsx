import type { Lang } from "@/lib/contract";
import { t } from "@/lib/i18n";

/** DSP- = dispute filed (green, only shown once the read-back confirmed it); anything else (HND-) is a plain reference. */
export function Receipt({ refId, lang }: { refId: string; lang: Lang }) {
  const d = t(lang);
  const filed = refId.startsWith("DSP-");
  return (
    <span className={`inline-flex items-center gap-1.5 self-start rounded-full px-3 py-1.5 text-sm font-bold tabular-nums ${filed ? "bg-b-receipt text-b-receipt-ink" : "bg-b-mist text-b-cobalt"}`}>
      {filed && <span aria-hidden>✓</span>}
      <span>{filed ? d.disputeFiled(refId) : d.reference(refId)}</span>
    </span>
  );
}
