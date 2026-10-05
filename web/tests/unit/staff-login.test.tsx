// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StaffLogin } from "@/components/staff/StaffLogin";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
const STAFF = [{ username: "agent.ana", demo_password: "staff-ana-demo", display_name: "Ana R." }];

beforeEach(() => { cleanup(); replace.mockReset(); });

describe("StaffLogin", () => {
  it("signs in the picked staff identity and goes to next", async () => {
    const f = vi.fn(async (url: string) => url.startsWith("/api/auth/demo-users") ? Response.json({ data: STAFF }) : Response.json({ data: { name: "Ana R." } }));
    vi.stubGlobal("fetch", f);
    render(<StaffLogin next="/agent/HND-1" />);
    await screen.findByRole("option", { name: /Ana R\./ });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/agent/HND-1"));
    const call = f.mock.calls.find(([u]) => u === "/api/auth/staff-login") as unknown as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toEqual({ username: "agent.ana", password: "staff-ana-demo" });
  });
  it("shows a plain error when rejected", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.startsWith("/api/auth/demo-users") ? Response.json({ data: STAFF })
      : Response.json({ error: { code: "login_failed", message: "x" } }, { status: 401 })));
    render(<StaffLogin next="/agent" />);
    await screen.findByRole("option", { name: /Ana R\./ });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("didn't work");
    expect(replace).not.toHaveBeenCalled();
  });
});
