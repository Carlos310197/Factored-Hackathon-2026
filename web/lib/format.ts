import type { Lang } from "./contract";

const MONEY_LOCALE: Record<Lang, (currency: string) => string> = {
  es: (c) => (c === "COP" ? "es-CO" : c === "ARS" ? "es-AR" : "es-MX"),
  pt: () => "pt-BR",
};

/** Money by currency code (agent-core spec §6.3): COP without decimals, everything else with 2. */
export function fmtMoney(amount: number, currency: string, lang: Lang): string {
  const digits = currency === "COP" ? 0 : 2;
  const n = new Intl.NumberFormat(MONEY_LOCALE[lang](currency), {
    minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always",
  }).format(amount);
  return `${currency} ${n}`;
}

export function fmtDate(isoDate: string, lang: Lang): string {
  const [y, m, d] = isoDate.slice(0, 10).split("-").map(Number);
  return new Intl.DateTimeFormat(lang === "pt" ? "pt-BR" : "es-MX", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  }).format(new Date(Date.UTC(y, m - 1, d)));
}

export function fmtAge(fromIso: string, now: Date = new Date()): string {
  const mins = Math.max(0, Math.floor((now.getTime() - new Date(fromIso).getTime()) / 60_000));
  if (mins < 60) return `${mins} min`;
  if (mins < 60 * 24) return `${Math.floor(mins / 60)} h`;
  return `${Math.floor(mins / (60 * 24))} d`;
}

/** Message time in the viewer's own timezone ("" when the stamp can't be read). */
export function fmtTime(iso: string, lang: Lang, timeZone?: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat(lang === "pt" ? "pt-BR" : "es-MX", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone }).format(d);
}
