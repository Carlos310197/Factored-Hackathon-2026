// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/customer/LoginForm";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

const USERS = [
  { username: "ana.mx", demo_password: "demo-ana", otp: "123456", lang: "es", role: "customer", display_name: "", scenarios: [] },
  { username: "rui.pt", demo_password: "demo-rui", otp: "111111", lang: "pt", role: "customer", display_name: "", scenarios: [] },
];
function mockFetch(otpStatus = 200) {
  return vi.fn(async (url: string) => {
    if (url.startsWith("/api/auth/demo-users")) return Response.json({ data: USERS });
    if (url === "/api/auth/login") return Response.json({ data: { login_ticket: "tk" } });
    if (url === "/api/auth/otp") return otpStatus === 200 ? Response.json({ data: { lang: "es", expires_in: 900 } })
      : Response.json({ error: { code: "otp_failed", message: "x" } }, { status: otpStatus });
    return new Response(null, { status: 404 });
  });
}

beforeEach(() => { cleanup(); replace.mockReset(); });

describe("LoginForm", () => {
  it("filters identities by language and switches the copy", async () => {
    vi.stubGlobal("fetch", mockFetch());
    render(<LoginForm next="/chat" embed={false} />);
    expect(await screen.findByRole("heading", { name: "Hola, entra para hablar con el asistente" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Português" }));
    expect(screen.getByRole("heading", { name: "Olá, entre para falar com o assistente" })).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveDisplayValue(/rui\.pt/);
    expect(document.documentElement.lang).toBe("pt");
  });
  it("signs in with password then the shown OTP and goes to next", async () => {
    const f = mockFetch();
    vi.stubGlobal("fetch", f);
    render(<LoginForm next="/chat" embed={false} />);
    await userEvent.click(await screen.findByRole("button", { name: "Continuar" }));
    await userEvent.click(await screen.findByRole("button", { name: "Entrar" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/chat"));
    const otpCall = f.mock.calls.find(([u]) => u === "/api/auth/otp") as unknown as [string, RequestInit];
    expect(JSON.parse(String(otpCall[1].body))).toEqual({ login_ticket: "tk", otp: "123456", short_ttl: false });
  });
  it("shows a plain error when the code is rejected", async () => {
    vi.stubGlobal("fetch", mockFetch(401));
    render(<LoginForm next="/chat" embed={false} />);
    await userEvent.click(await screen.findByRole("button", { name: "Continuar" }));
    await userEvent.click(await screen.findByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos verificar tus datos");
  });
});
