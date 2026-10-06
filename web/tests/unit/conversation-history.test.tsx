// @vitest-environment jsdom
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatScreen } from "@/components/customer/ChatScreen";
import { sessionsApi } from "@/lib/chat/api";

const replace = vi.fn();
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, refresh }), redirect: vi.fn() }));
vi.mock("@/lib/server/session", () => ({ customerFromCookies: async () => ({ sid: "S-NEW", lang: "pt" }) }));
class RO { observe() {} unobserve() {} disconnect() {} }
globalThis.ResizeObserver ??= RO as unknown as typeof ResizeObserver;
Element.prototype.scrollTo ??= () => {};
afterEach(() => { cleanup(); vi.unstubAllGlobals(); replace.mockReset(); refresh.mockReset(); });

const summary = (o: object) => ({ session_id: "S-1", created_at: "2026-10-06T14:05:00Z", language: "es", current: false, ended: false, preview: null, ...o });
const LIST = [
  summary({ session_id: "S-CUR", current: true, preview: "Hola de nuevo" }),
  summary({ session_id: "S-OLD", ended: true, preview: "Me cobraron dos veces", created_at: "2026-10-01T09:00:00Z" }),
  summary({ session_id: "S-EMPTY", preview: null }),
];
const msg = (id: string, role: string, text: string) => ({ id, cursor: `0${id}`, role, text, ts: "2026-10-01T09:00:00Z" });

type Route = (method: string, url: string) => { status?: number; body: unknown } | undefined;
function mockFetch(route: Route = () => undefined) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const r = route(method, String(url));
    if (r) return Response.json(r.body, { status: r.status ?? 200 });
    if (String(url) === "/api/customer/sessions") return Response.json({ data: LIST });
    if (String(url).includes("/S-OLD/messages")) return Response.json({ data: [msg("1", "customer", "Me cobraron dos veces"), msg("2", "assistant", "Revisemos ese cargo.")] });
    if (String(url).includes("/messages")) return Response.json({ data: [] });
    return new Response(null, { status: 202 });
  });
  vi.stubGlobal("fetch", f);
  return f;
}
const calls = (f: ReturnType<typeof mockFetch>, url: string, method = "POST") =>
  (f.mock.calls as unknown[][]).filter(([u, i]) => u === url && ((i as RequestInit | undefined)?.method ?? "GET") === method);

async function openHistory(lang: "es" | "pt" = "es") {
  render(<ChatScreen sid="S-CUR" lang={lang} embed={false} />);
  const trigger = screen.getByRole("button", { name: lang === "es" ? "Conversaciones" : "Conversas" });
  await userEvent.click(trigger);
  const dialog = await screen.findByRole("dialog", { name: lang === "es" ? "Conversaciones" : "Conversas" });
  await within(dialog).findByText("Me cobraron dos veces");
  return { dialog, trigger };
}

describe("sessionsApi", () => {
  it("parses the list, maps 401 to expired and a bad body to error", async () => {
    mockFetch();
    const r = await sessionsApi.list();
    expect(r.kind === "ok" && r.data[0]).toMatchObject({ session_id: "S-CUR", current: true, preview: "Hola de nuevo" });
    mockFetch(() => ({ status: 401, body: { error: { code: "session_expired", message: "" } } }));
    expect(await sessionsApi.list()).toEqual({ kind: "expired" });
    mockFetch(() => ({ body: { data: [{ session_id: 1 }] } }));
    expect(await sessionsApi.list()).toEqual({ kind: "error", code: undefined });
  });
  it("hide surfaces the error code (409 current_session)", async () => {
    mockFetch(() => ({ status: 409, body: { error: { code: "current_session", message: "" } } }));
    expect(await sessionsApi.hide("S-CUR")).toEqual({ kind: "error", code: "current_session" });
  });
});

describe("conversation history drawer", () => {
  it("lists conversations with previews, a fallback, Actual and Terminada tags", async () => {
    mockFetch();
    const { dialog } = await openHistory();
    const rows = within(dialog).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText("Actual")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Terminada")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Sin mensajes")).toBeInTheDocument();
  });

  it("opens a past conversation read-only, with no composer, and goes back", async () => {
    mockFetch();
    const { dialog } = await openHistory();
    await userEvent.click(within(dialog).getByRole("button", { name: /Me cobraron dos veces/ }));
    expect(await within(dialog).findByText("Revisemos ese cargo.")).toBeInTheDocument();
    expect(within(dialog).getByText("Conversación anterior · solo lectura")).toBeInTheDocument();
    expect(within(dialog).queryByRole("textbox")).not.toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Volver" }));
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(3);
  });

  it("tapping the current conversation closes the drawer; Escape closes and focus returns", async () => {
    mockFetch();
    const { dialog, trigger } = await openHistory();
    await userEvent.click(within(dialog).getByRole("button", { name: /Hola de nuevo/ }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(trigger);
    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("hide is offered only for past ones, confirms, then removes the row", async () => {
    const f = mockFetch((m, u) => (m === "POST" && u.endsWith("/hide") ? { body: { data: { hidden: true } } } : undefined));
    const { dialog } = await openHistory();
    const rows = within(dialog).getAllByRole("listitem");
    expect(within(rows[0]).queryByRole("button", { name: "Ocultar de mi lista" })).not.toBeInTheDocument();
    await userEvent.click(within(rows[1]).getByRole("button", { name: "Ocultar de mi lista" }));
    expect(calls(f, "/api/customer/sessions/S-OLD/hide")).toHaveLength(0);
    await userEvent.click(within(rows[1]).getByRole("button", { name: "Ocultar" }));
    await waitFor(() => expect(within(dialog).getAllByRole("listitem")).toHaveLength(2));
    expect(calls(f, "/api/customer/sessions/S-OLD/hide")).toHaveLength(1);
    expect(within(dialog).queryByText("Me cobraron dos veces")).not.toBeInTheDocument();
  });

  it("end → ended state without a composer → new conversation calls /new and refreshes to the new sid", async () => {
    const f = mockFetch((m, u) => {
      if (m === "POST" && u === "/api/customer/sessions/end") return { body: { data: { ended: true } } };
      if (m === "POST" && u === "/api/customer/sessions/new") return { body: { data: { session_id: "S-NEW", lang: "es", expires_in: 3600 } } };
    });
    const { dialog } = await openHistory();
    await userEvent.click(within(dialog).getByRole("button", { name: "Terminar conversación" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Terminar" }));
    expect(await screen.findByText("Conversación terminada")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Escribe un mensaje…")).not.toBeInTheDocument();
    expect(calls(f, "/api/customer/sessions/end")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Nueva conversación" }));
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(calls(f, "/api/customer/sessions/new")).toHaveLength(1);
  });

  it("a 409 session_ended from the chat shows the ended state; Salir signs out", async () => {
    mockFetch((m, u) => (m === "POST" && u === "/api/chat" ? { status: 409, body: { error: { code: "session_ended", message: "" } } } : undefined));
    render(<ChatScreen sid="S-CUR" lang="pt" embed={false} />);
    await userEvent.type(screen.getByLabelText("Escreva uma mensagem…"), "oi{Enter}");
    expect(await screen.findByText("Conversa encerrada")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nova conversa" })).toBeInTheDocument();
    expect(screen.queryByText("Não conseguimos enviar sua mensagem.")).not.toBeInTheDocument();
    const banner = screen.getByText("Conversa encerrada").closest("section")!;
    await userEvent.click(within(banner).getByRole("button", { name: "Sair" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });

  it("speaks Portuguese: drawer title, tags, hide and end labels", async () => {
    mockFetch();
    const { dialog } = await openHistory("pt");
    expect(within(dialog).getByText("Atual")).toBeInTheDocument();
    expect(within(dialog).getByText("Encerrada")).toBeInTheDocument();
    expect(within(dialog).getByText("Sem mensagens")).toBeInTheDocument();
    expect(within(dialog).getAllByRole("button", { name: "Ocultar da minha lista" })).toHaveLength(2);
    expect(within(dialog).getByRole("button", { name: "Encerrar conversa" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Nova conversa" })).toBeInTheDocument();
  });
});

describe("/chat page", () => {
  it("keys the chat by sid so a new session remounts it with fresh state", async () => {
    const { default: ChatPage } = await import("@/app/chat/page");
    const el = await ChatPage({ searchParams: Promise.resolve({}) });
    expect(el.key).toBe("S-NEW");
    expect(el.props).toMatchObject({ sid: "S-NEW", lang: "pt" });
  });
});
