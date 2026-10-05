import AxeBuilder from "@axe-core/playwright";
import { expect, type BrowserContext, type Page } from "@playwright/test";

export const BASE = "http://localhost:3200";
export async function signInCustomer(ctx: BrowserContext, lang: "es" | "pt" = "es") {
  await ctx.addCookies([{ name: "cust_session", value: `e2e.customer.CLI-A.S-1.${lang}`, url: BASE }]);
}
export async function signInStaff(ctx: BrowserContext) {
  await ctx.addCookies([{ name: "staff_session", value: "e2e.staff.agent.ana.Ana R.", url: BASE }]);
}
type Handler = (req: { method: string; url: URL; body: unknown }) => { status?: number; json: unknown } | undefined;
export async function mockApi(page: Page, handler: Handler) {
  await page.context().route("**/api/**", async (route) => {
    const r = route.request();
    const url = new URL(r.url());
    const res = handler({ method: r.method(), url, body: r.postDataJSON?.() ?? null });
    if (!res) return route.fulfill({ status: 404, json: { error: { code: "not_found", message: url.pathname } } });
    return route.fulfill({ status: res.status ?? 200, json: res.json });
  });
}
export async function noSeriousA11y(page: Page) {
  const r = await new AxeBuilder({ page }).analyze();
  const bad = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => `${n.target} ${n.any[0]?.message ?? ""}`).join(" | ")}`)).toEqual([]);
}
export const msg = (id: string, role: string, text: string, extra: Record<string, unknown> = {}) =>
  ({ id, cursor: `2026-09-30T10:00:0${id.length % 10}.000000+00:00#${id}`, role, text, ts: "2026-09-30T10:00:00Z", ...extra });
