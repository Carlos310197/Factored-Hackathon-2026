// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AsOfBanner } from "@/components/customer/AsOfBanner";
import { CaseHeader } from "@/components/staff/CaseHeader";
import { TraceList } from "@/components/trace/TraceList";
import { LoginForm } from "@/components/customer/LoginForm";
import { createChatStore } from "@/lib/chat/store";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/lib/realtime/useChannel", () => ({ useChannel: () => "live" }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("UI polish", () => {
  it("the customer row stops saying 'sending' once its reply is in", () => {
    const s = createChatStore();
    s.getState().sendOptimistic("cm-1", "saldo");
    s.getState().applyReply("cm-1", { reply_text: "ok", language: "es", awaiting: "none", options: [], refs: [], data_as_of: null, turn_id: "TRN-1" });
    expect(s.getState().messages.find((m) => m.id === "cm-1")?.status).toBe("sent");
    expect(s.getState().cursor).toBeNull();
  });
  it("the as-of banner keeps its row before the date is known (no layout jump)", () => {
    const { container } = render(<AsOfBanner date={null} lang="es" />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });
  it("case actions show a busy state while the request runs", () => {
    const packet = { handoff_id: "HND-1", status: "claimed", claimed_by: "agent.ana", priority: "high", customer_id: "C", language: "es",
      data_as_of: "2026-06-17", session_id: "S", created_at: "2026-09-30T14:02:00Z" } as never;
    render(<CaseHeader packet={packet} control="agent" me={{ sub: "agent.ana", name: "Ana" }} onAction={() => {}} pending="takeover" />);
    const b = screen.getByRole("button", { name: /Take over chat/ });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("aria-busy", "true");
  });
  it("trace says loading, not 'no turns', until the first fetch lands, and says when it fails", async () => {
    let fail: () => void = () => {};
    vi.stubGlobal("fetch", vi.fn(() => new Promise((_, rej) => { fail = () => rej(new Error("x")); })));
    render(<TraceList sid="S1" mode="console" />);
    expect(screen.getByText(/Loading trace/)).toBeInTheDocument();
    expect(screen.queryByText(/No turns yet/)).toBeNull();
    await act(async () => { fail(); });
    await waitFor(() => expect(screen.getByText(/Couldn.t load the trace/)).toBeInTheDocument());
  });
});

describe("login OTP step", () => {
  it("focuses the code field when the OTP step opens", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/demo-users"
      ? Response.json({ data: [{ username: "ana", demo_password: "p", otp: "123456", lang: "es", role: "customer", display_name: "Ana", scenarios: [] }] })
      : Response.json({ data: { login_ticket: "tk" } })));
    render(<LoginForm next="/chat" embed={false} />);
    await userEvent.click(await screen.findByRole("button", { name: "Continuar" }));
    await waitFor(() => expect(screen.getByLabelText(/código/i)).toHaveFocus());
  });
});
