// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/customer/LoginForm";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); replace.mockReset(); });

const USERS = [{ username: "ana.mx", demo_password: "demo-ana", otp: "123456", lang: "es" as const, role: "customer", display_name: "Ana Pérez", scenarios: [] }];
const api = () => vi.fn(async (url: string) => url === "/api/auth/login" ? Response.json({ data: { login_ticket: "tk" } })
  : url === "/api/auth/otp" ? Response.json({ data: { lang: "es", expires_in: 900 } }) : Response.json({ data: USERS }));

describe("login speed and the code step", () => {
  it("users handed in by the server fill the form on first paint, with no client fetch", () => {
    const f = api();
    vi.stubGlobal("fetch", f);
    render(<LoginForm next="/chat" embed={false} initialUsers={USERS} />);
    expect(screen.getByRole("combobox")).toHaveDisplayValue(/ana\.mx/);
    expect(screen.getByLabelText("Contraseña")).toHaveValue("demo-ana");
    expect(f).not.toHaveBeenCalled();
  });
  it("the code step names who is signing in and can go back to change user", async () => {
    vi.stubGlobal("fetch", api());
    render(<LoginForm next="/chat" embed={false} initialUsers={USERS} />);
    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));
    expect(await screen.findByText(/Entrando como Ana Pérez/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cambiar" }));
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });
  it("keeps digits only and signs in as soon as six are typed", async () => {
    const f = api();
    vi.stubGlobal("fetch", f);
    render(<LoginForm next="/chat" embed={false} initialUsers={USERS} />);
    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));
    const code = await screen.findByLabelText("Código");
    await userEvent.clear(code);
    await userEvent.type(code, "12a3456");
    expect(code).toHaveValue("123456");
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/chat"));
    const otpCalls = f.mock.calls.filter(([u]) => u === "/api/auth/otp");
    expect(otpCalls).toHaveLength(1);
  });
});
