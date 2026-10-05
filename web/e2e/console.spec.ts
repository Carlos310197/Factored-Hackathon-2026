import { expect, test } from "@playwright/test";
import { mockApi, msg, noSeriousA11y, signInStaff } from "./fixtures";

const PACKET = (status: string, claimed_by: string | null) => ({ schema_version: "handoff.v1", handoff_id: "HND-7Q2K", created_at: "2026-09-30T14:02:00Z",
  status, claimed_by, session_id: "S-1", customer_id: "CLI-0421", language: "es", data_as_of: "2026-06-17", priority: "critical",
  reason_codes: ["reports_unauthorized_use"], customer_request: { original: "No reconozco un cargo de $420 en Amazon", en: "I don't recognize a $420 Amazon charge" },
  verified_facts: [{ fact: "Amazon · USD 420.00 · 2 Jun 2026 · Approved", receipt_id: "r-114" }], actions_taken: [], decisions: [],
  policy_checks: [{ rule: "within_60_days", passed: true }, { rule: "fraud_score_ok", passed: false }], open_questions: ["¿Todavía tiene la tarjeta?"], transcript_ref: "session:S-1" });

test("claim → take over → message → return → resolve", async ({ page, context }) => {
  await signInStaff(context);
  let status = "open"; let holder: string | null = null; let control = "agent";
  const transcript = [msg("m1", "customer", "No reconozco un cargo de $420 en Amazon")];
  await mockApi(page, ({ method, url, body }) => {
    const p = url.pathname;
    if (p === "/api/handoffs") return { json: { data: [{ handoff_id: "HND-7Q2K", session_id: "S-1", status, priority: "critical", reason_codes: ["reports_unauthorized_use"], language: "es", created_at: "2026-09-30T14:02:00Z", claimed_by: holder }] } };
    if (p === "/api/handoffs/HND-7Q2K") return { json: { data: { packet: PACKET(status, holder), control } } };
    if (p.startsWith("/api/handoffs/HND-7Q2K/") && method === "POST") {
      const a = p.split("/").pop();
      if (a === "claim") { status = "claimed"; holder = "agent.ana"; }
      if (a === "takeover") { status = "in_takeover"; control = "human:agent.ana"; }
      if (a === "return") { status = "returned"; control = "agent"; }
      if (a === "resolve") { status = "resolved"; }
      return { json: { data: PACKET(status, holder) } };
    }
    if (p === "/api/trace/S-1") return { json: { data: [] } };
    if (p === "/api/sessions/S-1/messages" && method === "GET") return { json: { data: transcript } };
    if (p === "/api/sessions/S-1/messages" && method === "POST") {
      transcript.push(msg("m2", "agent", (body as { text: string }).text, { author: "Ana R." }));
      return { status: 201, json: { data: transcript.at(-1) } };
    }
  });
  await page.goto("/agent/HND-7Q2K");
  await expect(page.getByText("Verified facts")).toBeVisible();
  await noSeriousA11y(page);
  await page.getByRole("button", { name: "Claim" }).click();
  await page.getByRole("button", { name: "Take over chat" }).click();
  await expect(page.getByRole("tab", { name: "Conversation", selected: true })).toBeVisible();
  await page.getByLabel("Message to the customer").fill("Hola, soy Ana. ¿Todavía tienes la tarjeta?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Hola, soy Ana. ¿Todavía tienes la tarjeta?")).toBeVisible();
  await page.getByRole("button", { name: "Return to assistant" }).click();
  await page.getByRole("button", { name: "Resolve…" }).click();
  await page.getByLabel("Outcome").selectOption("resolved_by_agent");
  await page.getByRole("button", { name: "Resolve case" }).click();
  await expect(page.getByText(/Critical · resolved/)).toBeVisible();
});

test("trace page renders turns and passes the a11y scan", async ({ page, context }) => {
  await signInStaff(context);
  await mockApi(page, ({ url }) => url.pathname === "/api/trace/S-1" ? { json: { data: [{ turnId: "T1", quote: "saldo", quoteEn: "balance", durationMs: 1200,
    bars: [{ signal: "intent", label: "Intent", value: 0.91, threshold: 0.8, crossed: true, color: "#2a78d6", verdict: { icon: "✓", text: "act" } }],
    folded: { count: 0, highest: null, bars: [] }, replyCheck: null, errors: [], route: { next: "answer_inquiry", priority: null, policy: [] }, versions: {} }] } } : undefined);
  await page.goto("/trace/S-1");
  await expect(page.getByText("Route: answer_inquiry")).toBeVisible();
  await noSeriousA11y(page);
});
