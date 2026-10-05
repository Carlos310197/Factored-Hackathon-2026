// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AsOfBanner } from "@/components/customer/AsOfBanner";
import { ChatScreen } from "@/components/customer/ChatScreen";
import { Chips } from "@/components/customer/Chips";
import { ConfirmCard } from "@/components/customer/ConfirmCard";
import { ExpiredSheet } from "@/components/customer/ExpiredSheet";
import { Receipt } from "@/components/customer/Receipt";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
class RO { observe() {} unobserve() {} disconnect() {} }
globalThis.ResizeObserver ??= RO as unknown as typeof ResizeObserver;
Element.prototype.scrollTo ??= () => {};
afterEach(() => { cleanup(); vi.unstubAllGlobals(); replace.mockReset(); });

describe("customer parts", () => {
  it("chips send the option text", async () => {
    const onPick = vi.fn();
    render(<Chips options={["Reclamar un cargo", "Pago rechazado"]} disabled={false} onPick={onPick} />);
    await userEvent.click(screen.getByRole("button", { name: "Pago rechazado" }));
    expect(onPick).toHaveBeenCalledWith("Pago rechazado");
  });
  it("the confirmation card shows the draft formatted in the locale and confirms", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmCard lang="es" disabled={false} onConfirm={onConfirm} onChange={vi.fn()}
      summary={{ merchant: "Éxito Laureles", date: "2026-06-03", amount: 184900, currency: "COP", reason_code: "duplicate_charge" }} />);
    expect(screen.getByRole("heading", { name: "Resumen de tu disputa" })).toBeInTheDocument();
    expect(screen.getByText("COP 184.900")).toBeInTheDocument();
    expect(screen.getByText("Cargo duplicado")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar y enviar" }));
    expect(onConfirm).toHaveBeenCalled();
  });
  it("the confirmation card skips a null amount instead of inventing one", () => {
    render(<ConfirmCard lang="es" disabled={false} onConfirm={vi.fn()} onChange={vi.fn()}
      summary={{ merchant: "Rappi", date: "2026-06-03", amount: null, currency: null, reason_code: null }} />);
    expect(screen.getByText("Rappi")).toBeInTheDocument();
    expect(screen.queryByText("Monto")).not.toBeInTheDocument();
  });
  it("receipts distinguish a filed dispute from a handoff reference", () => {
    render(<><Receipt refId="DSP-01J9Z4" lang="pt" /><Receipt refId="HND-7Q2K" lang="es" /></>);
    expect(screen.getByText("Contestação DSP-01J9Z4 · enviada")).toBeInTheDocument();
    expect(screen.getByText("Referencia HND-7Q2K")).toBeInTheDocument();
  });
  it("the as-of banner is localised", () => {
    render(<AsOfBanner date="2026-06-17" lang="pt" />);
    expect(screen.getByText(/^Informações de 17/)).toBeInTheDocument();
  });
  it("the expired sheet is a labelled modal with a sign-in action", async () => {
    render(<ExpiredSheet lang="es" embed={true} />);
    expect(screen.getByRole("dialog", { name: "Tu sesión terminó" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Entrar de nuevo" }));
    expect(replace).toHaveBeenCalledWith("/login?next=/chat&embed=1");
  });
});

describe("ChatScreen", () => {
  const msg = (over: object) => ({ id: "m1", cursor: "0001", role: "assistant", text: "hola", ts: "2026-06-17T10:00:00Z", ...over });
  function mockFetch(history: object[], status = 200) {
    const f = vi.fn(async (url: string) => {
      if (String(url).includes("/messages")) return status === 200 ? Response.json({ data: history }) : Response.json({ error: { code: "x", message: "x" } }, { status });
      return new Response(null, { status: 202 });
    });
    vi.stubGlobal("fetch", f);
    return f;
  }

  it("Salir/Sair posts customer logout then goes to /login; hidden in embed", async () => {
    const f = mockFetch([]);
    render(<ChatScreen sid="s1" lang="pt" embed={false} />);
    await userEvent.click(screen.getByRole("button", { name: "Sair" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    const call = (f.mock.calls as unknown[][]).find(([u]) => u === "/api/auth/logout")!;
    expect(JSON.parse(String((call[1] as RequestInit).body))).toEqual({ who: "customer" });
    cleanup();
    render(<ChatScreen sid="s1" lang="es" embed={true} />);
    expect(screen.queryByRole("button", { name: "Salir" })).not.toBeInTheDocument();
  });

  it("renders history: chips, receipts and the as-of banner; tapping a chip posts it", async () => {
    const f = mockFetch([
      msg({ id: "a", cursor: "0001", text: "¿Qué necesitas?", meta: { awaiting: "clarification", options: ["Reclamar un cargo"], refs: ["HND-7Q2K"], data_as_of: "2026-06-17" } }),
    ]);
    render(<ChatScreen sid="s1" lang="es" embed={false} />);
    const chip = await screen.findByRole("button", { name: "Reclamar un cargo" });
    expect(screen.getByText("Referencia HND-7Q2K")).toBeInTheDocument();
    expect(screen.getByText(/^Información al 17/)).toBeInTheDocument();
    await userEvent.click(chip);
    await waitFor(() => expect(f.mock.calls.some(([u, i]: unknown[]) => u === "/api/chat" && String((i as RequestInit | undefined)?.body).includes("Reclamar un cargo"))).toBe(true));
    expect(screen.getByText("Reclamar un cargo", { selector: "p" })).toBeInTheDocument();  // in the transcript
  });

  it("a history 401 shows the sign-in sheet and keeps the conversation", async () => {
    mockFetch([], 401);
    render(<ChatScreen sid="s1" lang="es" embed={false} />);
    expect(await screen.findByRole("dialog", { name: "Tu sesión terminó" })).toBeInTheDocument();
  });

  it("system lines render control and async failures without changing control", async () => {
    mockFetch([
      msg({ id: "s1", cursor: "0001", role: "system", text: "x", meta: { control: "human", agent_name: "Ana" } }),
      msg({ id: "s2", cursor: "0002", role: "system", text: "No pudimos procesar tu mensaje", meta: { error_code: "agent_failed" } }),
    ]);
    render(<ChatScreen sid="s1" lang="es" embed={true} />);
    expect(await screen.findByText("Ana, del equipo de LATAM Bank, se unió")).toBeInTheDocument();
    expect(screen.getByText("No pudimos procesar tu mensaje")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "LATAM Bank" })).not.toBeInTheDocument();  // embed hides chrome
  });

  it("a 202 keeps the typing indicator until the reply arrives, then clears it", async () => {
    let history: object[] = [];
    let clientId = "";
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes("/messages")) return Response.json({ data: history });
      clientId = JSON.parse(String(init?.body)).client_message_id;  // the server stores the question under this id
      return new Response(null, { status: 202 });
    }));
    render(<ChatScreen sid="s1" lang="es" embed={false} />);
    await userEvent.type(screen.getByRole("textbox"), "hola{Enter}");
    expect(await screen.findByText("El asistente está escribiendo")).toBeInTheDocument();
    history = [msg({ id: clientId, cursor: "0008", role: "customer", text: "hola" }), msg({ id: "a1", cursor: "0009", text: "Listo" })];
    await waitFor(() => expect(screen.getByText("Listo")).toBeInTheDocument(), { timeout: 5000 });
    expect(screen.queryByText("El asistente está escribiendo")).not.toBeInTheDocument();
  });

  it("the chat column is inert behind the expired sheet", async () => {
    mockFetch([], 401);
    const { container } = render(<ChatScreen sid="s1" lang="es" embed={false} />);
    await screen.findByRole("dialog", { name: "Tu sesión terminó" });
    expect(container.querySelector("[inert]")).toContainElement(screen.getByRole("textbox", { hidden: true }));
  });

  it("a second handoff shows the waiting line again", async () => {
    mockFetch([
      msg({ id: "a", cursor: "0001", meta: { awaiting: "human" } }),
      msg({ id: "c1", cursor: "0002", role: "system", text: "x", meta: { control: "human:ana", agent_name: "Ana" } }),
      msg({ id: "c2", cursor: "0003", role: "system", text: "x", meta: { control: "agent" } }),
      msg({ id: "b", cursor: "0004", text: "de vuelta", meta: { awaiting: "human" } }),
    ]);
    render(<ChatScreen sid="s1" lang="es" embed={false} />);
    expect(await screen.findByText("Una persona del equipo continuará esta conversación")).toBeInTheDocument();
  });
});
