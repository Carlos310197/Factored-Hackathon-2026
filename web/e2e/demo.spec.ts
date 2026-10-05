import { expect, test } from "@playwright/test";
import { mockApi, noSeriousA11y, signInCustomer, signInStaff } from "./fixtures";

test("acts 1–3", async ({ page, context }) => {
  await signInStaff(context);
  await signInCustomer(context);
  let turns: unknown[] = [];
  await mockApi(page, ({ url, method }) => {
    const p = url.pathname;
    if (p === "/api/auth/demo-users") return { json: { data: [{ username: "ana.mx", demo_password: "x", otp: "123456", lang: "es", role: "customer", display_name: "", scenarios: ["unauthorized_handoff"] }] } };
    if (p === "/api/auth/login") return { json: { data: { login_ticket: "tk" } } };
    if (p === "/api/auth/otp") return { json: { data: { lang: "es", expires_in: 900 } } };
    if (p === "/api/auth/debug-claims") return { json: { data: { sub: "CLI-A", sid: "S-1", lang: "es", scopes: ["dispute:create", "inquiry:read"], exp: Math.floor(Date.now() / 1000) + 900 } } };
    if (p === "/api/auth/logout") return { json: { data: { signed_out: "customer" } } };
    if (p === "/api/sessions/S-1/messages") return { json: { data: [] } };
    if (p === "/api/trace/S-1") return { json: { data: turns } };
    if (p === "/api/chat" && method === "POST") {
      turns = [{ turnId: "T1", quote: "saldo", quoteEn: "balance", durationMs: 1800, bars: [{ signal: "intent", label: "Intent", value: 0.91, threshold: 0.8,
        crossed: true, color: "#2a78d6", verdict: { icon: "✓", text: "act" } }], folded: { count: 7, highest: { label: "Distress", value: 0.04 }, bars: [] },
        replyCheck: { text: "Reply check 1/1 claims supported · no unverified promises", failed: false, regenerated: 0, template: false }, errors: [],
        route: { next: "answer_inquiry", priority: null, policy: [] }, versions: {} }];
      return { json: { data: { reply_text: "Tienes USD 1,240.50 disponibles.", language: "es", awaiting: "none", options: [], refs: [], data_as_of: "2026-06-17", turn_id: "T1" } } };
    }
  });
  await page.goto("/demo");
  const phone = page.frameLocator("iframe[title=\"Customer's phone\"]");
  await phone.getByRole("button", { name: "Continuar" }).click();
  await phone.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByText("CLI-A (sub)")).toBeVisible();
  await page.getByRole("button", { name: "2 · Live conversation" }).click();
  await phone.getByLabel("Escribe un mensaje…").fill("¿Cuánto tengo disponible?");
  await phone.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText("Route: answer_inquiry")).toBeVisible();
  await expect(page.getByText(/7 more signals below threshold/)).toBeVisible();
  await page.getByRole("button", { name: "3 · Scenarios" }).click();
  await expect(page.getByRole("button", { name: /dispute filed/i })).toBeDisabled();
  await page.getByRole("button", { name: /unauthorized → handoff/i }).click();
  await expect(page.getByRole("button", { name: /Put in composer: No reconozco/ })).toBeVisible();
  await noSeriousA11y(page);
});
