// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StaffSignOut } from "@/components/staff/StaffSignOut";
import { signOut } from "@/lib/signout";
import { t } from "@/lib/i18n";

const replace = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); replace.mockClear(); });

const body = (f: ReturnType<typeof vi.fn>) => JSON.parse(f.mock.calls[0][1].body);

describe("sign out", () => {
  it("staff button posts staff and goes to the staff login", async () => {
    const f = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", f);
    render(<StaffSignOut />);
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?staff=1"));
    expect(f.mock.calls[0][0]).toBe("/api/auth/logout");
    expect(body(f)).toEqual({ who: "staff" });
  });
  it("still navigates when the fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    render(<StaffSignOut />);
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?staff=1"));
  });
  it("posts customer", async () => {
    const f = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", f);
    await signOut("customer");
    expect(body(f)).toEqual({ who: "customer" });
  });
  it("has copy in es and pt", () => { expect(t("es").signOut).toBe("Salir"); expect(t("pt").signOut).toBe("Sair"); });
});
