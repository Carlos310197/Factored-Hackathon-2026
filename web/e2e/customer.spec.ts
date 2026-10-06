import { expect, test } from "@playwright/test";
import { mockApi, msg, noSeriousA11y, signInCustomer } from "./fixtures";

const reply = (o: Record<string, unknown>) => ({ data: { reply_text: "", language: "es", awaiting: "none", options: [], refs: [], data_as_of: "2026-06-17", turn_id: "TRN-1", ...o } });

test("clarify: options become chips and a tap sends the text", async ({ page, context }) => {
  await signInCustomer(context);
  const sent: string[] = [];
  await mockApi(page, ({ method, url, body }) => {
    if (url.pathname.endsWith("/messages")) return { json: { data: [] } };
    if (url.pathname === "/api/chat" && method === "POST") {
      sent.push((body as { message: string }).message);
      return sent.length === 1
        ? { json: reply({ reply_text: "¿Es un cargo que quieres reclamar, o un pago rechazado?", awaiting: "clarification", options: ["Reclamar un cargo", "Pago rechazado"] }) }
        : { json: reply({ reply_text: "Veamos el pago rechazado.", turn_id: "TRN-2" }) };
    }
  });
  await page.goto("/chat");
  await page.getByLabel("Escribe un mensaje…").fill("Tengo un problema con un pago");
  await page.getByRole("button", { name: "Enviar" }).click();
  await page.getByRole("button", { name: "Pago rechazado" }).click();
  await expect(page.getByText("Veamos el pago rechazado.")).toBeVisible();
  expect(sent).toEqual(["Tengo un problema con un pago", "Pago rechazado"]);
  await noSeriousA11y(page);
});

test("confirm → filed: the card shows the draft, confirming shows the receipt", async ({ page, context }) => {
  await signInCustomer(context);
  let n = 0;
  await mockApi(page, ({ url, method }) => {
    if (url.pathname.endsWith("/messages")) return { json: { data: [] } };
    if (url.pathname === "/api/chat" && method === "POST") {
      n += 1;
      return n === 1
        ? { json: reply({ reply_text: "Encontré dos cargos iguales.", awaiting: "confirmation",
            summary: { merchant: "Éxito Laureles", date: "2026-06-03", amount: 184900, currency: "COP", reason_code: "duplicate_charge" } }) }
        : { json: reply({ reply_text: "Listo, registré tu disputa.", refs: ["DSP-01J9Z4"], turn_id: "TRN-2" }) };
    }
  });
  await page.goto("/chat");
  await page.getByLabel("Escribe un mensaje…").fill("Me cobraron dos veces en Éxito");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByRole("heading", { name: "Resumen de tu disputa" })).toBeVisible();
  await expect(page.getByText("COP 184.900")).toBeVisible();
  await page.getByRole("button", { name: "Confirmar y enviar" }).click();
  await expect(page.getByText("Disputa DSP-01J9Z4 · enviada")).toBeVisible();
});

test("handoff → takeover: reference chip, agent joins, agent message appears", async ({ page, context }) => {
  await signInCustomer(context);
  let history = [] as unknown[];
  await mockApi(page, ({ url, method }) => {
    if (url.pathname.endsWith("/messages")) return { json: { data: history } };
    if (url.pathname === "/api/chat" && method === "POST") {
      history = [msg("cm-x", "customer", "No reconozco un cargo"), msg("a1", "assistant", "Una persona revisará tu caso.", { turn_id: "TRN-1", meta: { refs: ["HND-7Q2K"] } }),
        msg("s1", "system", "Ana R., del equipo de LATAM Bank, se unió", { meta: { control: "human:agent.ana", agent_name: "Ana R." } }),
        msg("g1", "agent", "Hola, soy Ana. ¿Todavía tienes la tarjeta?", { author: "Ana R." })];
      return { json: reply({ reply_text: "Una persona revisará tu caso.", refs: ["HND-7Q2K"] }) };
    }
  });
  await page.goto("/chat");
  await page.getByLabel("Escribe un mensaje…").fill("No reconozco un cargo");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText("Referencia HND-7Q2K")).toBeVisible();
  await expect(page.getByText("Ana R., del equipo de LATAM Bank, se unió")).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("Ana R. · agente")).toBeVisible();
});

test("expired token: the sign-in sheet keeps the conversation", async ({ page, context }) => {
  await signInCustomer(context);
  await mockApi(page, ({ url }) => {
    if (url.pathname.endsWith("/messages")) return { json: { data: [msg("a0", "assistant", "Hola")] } };
    if (url.pathname === "/api/chat") return { status: 401, json: { error: { code: "session_expired", message: "x" } } };
  });
  await page.goto("/chat");
  await page.getByLabel("Escribe un mensaje…").fill("¿Cuál es mi saldo?");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByRole("dialog", { name: "Tu sesión terminó" })).toBeVisible();
  await expect(page.getByText("Hola")).toBeVisible();
});

test("login page has no serious accessibility issues", async ({ page }) => {
  await mockApi(page, ({ url }) => url.pathname === "/api/auth/demo-users"
    ? { json: { data: [{ username: "ana.mx", demo_password: "x", otp: "1", lang: "es", role: "customer", display_name: "", scenarios: [] }] } } : undefined);
  await page.goto("/login");
  await noSeriousA11y(page);
});

test("history: open the drawer, read a past conversation read-only, go back", async ({ page, context }) => {
  await signInCustomer(context);
  await mockApi(page, ({ url }) => {
    if (url.pathname === "/api/customer/sessions") return { json: { data: [
      { session_id: "S-1", created_at: "2026-10-06T14:05:00Z", language: "es", current: true, ended: false, preview: "Hola" },
      { session_id: "S-0", created_at: "2026-10-01T09:00:00Z", language: "es", current: false, ended: true, preview: "Me cobraron dos veces" },
    ] } };
    if (url.pathname === "/api/sessions/S-0/messages") return { json: { data: [msg("c0", "customer", "Me cobraron dos veces"), msg("a00", "assistant", "Revisemos ese cargo.")] } };
    if (url.pathname.endsWith("/messages")) return { json: { data: [] } };
  });
  await page.goto("/chat");
  await page.getByRole("button", { name: "Conversaciones" }).click();
  const drawer = page.getByRole("dialog", { name: "Conversaciones" });
  await expect(drawer.getByText("Terminada")).toBeVisible();
  await drawer.getByRole("button", { name: /Me cobraron dos veces/ }).click();
  await expect(drawer.getByText("Revisemos ese cargo.")).toBeVisible();
  await expect(drawer.getByText("Conversación anterior · solo lectura")).toBeVisible();
  await expect(drawer.getByRole("textbox")).toHaveCount(0);
  await noSeriousA11y(page);
  await drawer.getByRole("button", { name: "Volver" }).click();
  await expect(drawer.getByRole("listitem")).toHaveCount(2);
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
});

test("my cases: the header opens a sheet with the customer's disputes, Escape closes it", async ({ page, context }) => {
  await signInCustomer(context);
  await mockApi(page, ({ url }) => {
    if (url.pathname.endsWith("/messages")) return { json: { data: [] } };
    if (url.pathname === "/api/customer/cases") return { json: { data: [{ dispute_id: "DSP-1759658400000A1B2C3D4", status: "pending_review",
      created_at: "2026-10-05T10:00:00+00:00", reason: "duplicate_charge", amount: 184900, currency: "COP" }] } };
  });
  await page.goto("/chat");
  await page.getByRole("button", { name: "Mis casos" }).click();
  const sheet = page.getByRole("dialog", { name: "Mis casos" });
  await expect(sheet.getByText("En revisión")).toBeVisible();
  await expect(sheet.getByText("COP 184.900")).toBeVisible();
  await noSeriousA11y(page);
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
});
