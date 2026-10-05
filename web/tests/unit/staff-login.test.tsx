// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StaffLogin } from "@/components/staff/StaffLogin";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

beforeEach(() => { cleanup(); replace.mockReset(); });

describe("StaffLogin", () => {
  it("signs in typed staff credentials and never asks for published ones", async () => {
    const f = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(async () => Response.json({ data: { name: "Ana R." } }));
    vi.stubGlobal("fetch", f);
    render(<StaffLogin next="/agent/HND-1" />);
    await userEvent.type(screen.getByLabelText("Staff identity"), "agent.ana");
    await userEvent.type(screen.getByLabelText("Password"), "staff-ana-demo");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/agent/HND-1"));
    expect(f.mock.calls.map(([u]) => u)).toEqual(["/api/auth/staff-login"]);
    const call = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toEqual({ username: "agent.ana", password: "staff-ana-demo" });
  });
  it("shows a plain error when rejected", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ error: { code: "login_failed", message: "x" } }, { status: 401 })));
    render(<StaffLogin next="/agent" />);
    await userEvent.type(screen.getByLabelText("Staff identity"), "agent.ana");
    await userEvent.type(screen.getByLabelText("Password"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("didn't work");
  });
});
