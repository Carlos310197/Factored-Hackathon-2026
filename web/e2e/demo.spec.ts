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

test("act 4: the human-agent view and stats next to the phone", async ({ page, context }) => {
  await signInStaff(context);
  await signInCustomer(context);
  const now = Date.now();
  const row = { handoff_id: "HND-7Q2K", session_id: "S-1", status: "claimed", priority: "critical", reason_codes: ["unauthorized_use"], language: "es",
    created_at: new Date(now - 120_000).toISOString(), claimed_by: "agent.ana" };
  const packet = { ...row, schema_version: "handoff.v1", claimed_at: new Date(now - 78_000).toISOString(), customer_id: "CUS-0421", data_as_of: "2026-06-17",
    customer_request: { original: "No reconozco un cargo de $420 en Amazon, yo no hice esa compra", en: "I don't recognize a $420 charge at Amazon, I didn't make that purchase" },
    verified_facts: [{ fact: "Amazon · USD 420.00 · 2 Jun 2026 · Approved · POS", receipt_id: "r-114" }, { fact: "fraud_score 61 (above 30)", receipt_id: "r-114" }],
    actions_taken: [{ action: "Dispute drafted", result: "unauthorized · pending review", receipt_id: "r-117" }],
    decisions: [], policy_checks: [{ rule: "Owned by customer", passed: true }, { rule: "fraud_score ≤ 30", passed: false }],
    open_questions: ["Does the customer still have the card?"], transcript_ref: "t" };
  const turns = [{ turnId: "T1", quote: "No reconozco un cargo", quoteEn: null, durationMs: 3200, bars: [], folded: { count: 0, highest: null, bars: [] },
    replyCheck: { text: "", failed: false, regenerated: 0, template: false }, errors: [], route: { next: "handoff", priority: "critical", policy: [] }, versions: {} }];
  await mockApi(page, ({ url }) => {
    const p = url.pathname;
    if (p === "/api/auth/demo-users") return { json: { data: [{ username: "ana.mx", demo_password: "x", otp: "123456", lang: "es", role: "customer", display_name: "", scenarios: ["unauthorized_handoff"] }] } };
    if (p === "/api/auth/login") return { json: { data: { login_ticket: "tk" } } };
    if (p === "/api/auth/otp") return { json: { data: { lang: "es", expires_in: 900 } } };
    if (p === "/api/auth/debug-claims") return { json: { data: { sub: "CUS-0421", sid: "S-1", lang: "es", scopes: ["inquiry:read"], exp: Math.floor(now / 1000) + 900 } } };
    if (p === "/api/sessions/S-1/messages") return { json: { data: [] } };
    if (p === "/api/trace/S-1") return { json: { data: turns } };
    if (p === "/api/handoffs") return { json: { data: url.searchParams.get("filter") === "mine" ? [row] : [] } };
    if (p === "/api/handoffs/HND-7Q2K") return { json: { data: { packet, control: "assistant" } } };
  });
  await page.goto("/demo");
  const phone = page.frameLocator("iframe[title=\"Customer's phone\"]");
  await phone.getByRole("button", { name: "Continuar" }).click();
  await phone.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByText("CUS-0421 (sub)")).toBeVisible();
  await page.getByRole("button", { name: "4 · Handoff" }).click();
  await expect(page.getByRole("heading", { name: /HND-7Q2K/ })).toBeVisible();
  await expect(page.getByRole("list", { name: "Conversation stats" })).toContainText("claimed 42 s after handoff");
  await expect(page.getByText(/Disputes today/)).toBeVisible();
  if (process.env.SHOT) await page.screenshot({ path: `${process.env.SHOT}-act4.png`, fullPage: true });
  await noSeriousA11y(page);
  await page.goto("/agent/HND-7Q2K");
  await expect(page.getByRole("button", { name: "Mine 1" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Conversation stats" })).toContainText("1 turn");
  if (process.env.SHOT) await page.screenshot({ path: `${process.env.SHOT}-agent.png`, fullPage: true });
  await noSeriousA11y(page);
});
