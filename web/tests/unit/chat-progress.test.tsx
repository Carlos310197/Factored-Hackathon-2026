// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { ChatScreen } from "@/components/customer/ChatScreen";

let push: (p: unknown) => void = () => {};
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/lib/realtime/useChannel", () => ({ useChannel: (_c: string, cb: (p: unknown) => void) => { push = cb; return "live"; } }));
class RO { observe() {} unobserve() {} disconnect() {} }
globalThis.ResizeObserver ??= RO as unknown as typeof ResizeObserver;
Element.prototype.scrollTo ??= () => {};
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("the typing indicator follows progress events (es)", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) =>
    String(url).includes("/messages") ? Response.json({ data: [] }) : new Response(null, { status: 202 })));
  render(<ChatScreen sid="s1" lang="es" embed={false} />);
  await userEvent.type(screen.getByRole("textbox"), "hola{Enter}");
  expect(await screen.findByText("El asistente está escribiendo")).toBeInTheDocument();
  act(() => push({ type: "progress", turn_id: "T", stage: "understand" }));
  expect(screen.getByText("Entendiendo tu mensaje…")).toBeInTheDocument();
  act(() => push({ type: "progress", turn_id: "T", stage: "verify" }));
  expect(screen.getByText("Verificando la respuesta…")).toBeInTheDocument();
});
