// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Console } from "@/components/staff/Console";

const redirect = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/lib/staff/redirect", () => ({ redirectToStaffLogin: redirect }));
vi.mock("@/lib/realtime/useChannel", () => ({ useChannel: () => "polling" }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const row = (id: string) => ({ handoff_id: id, session_id: "S", status: "open", priority: "high", reason_codes: ["asks_for_human"], language: "es", created_at: new Date().toISOString() });
const packet = (id: string) => ({ schema_version: "handoff.v1", handoff_id: id, created_at: new Date().toISOString(), status: "open", session_id: "S", customer_id: "CLI-1",
  language: "es", data_as_of: "2026-06-17", priority: "high", reason_codes: [], customer_request: { original: "x", en: "x" }, verified_facts: [], actions_taken: [],
  decisions: [], policy_checks: [], open_questions: [], transcript_ref: "t" });
const me = { sub: "agent.ana", name: "Ana R." };

describe("Console", () => {
  it("sends an expired staff session to the staff login", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ error: { code: "unauthorized", message: "x" } }, { status: 401 })));
    render(<Console me={me} />);
    await waitFor(() => expect(redirect).toHaveBeenCalled());
  });

  it("says so when the case does not exist", async () => {
    vi.stubGlobal("fetch", vi.fn(async (u: string) => u.startsWith("/api/handoffs?") ? Response.json({ data: [] })
      : Response.json({ error: { code: "not_found", message: "x" } }, { status: 404 })));
    render(<Console me={me} initialId="HND-NOPE" />);
    expect(await screen.findByText("This case no longer exists.")).toBeInTheDocument();
    expect(screen.queryByText("Loading case…")).toBeNull();
  });

  it("ignores a stale case response after another case is selected", async () => {
    let release!: () => void;
    const slowA = new Promise<void>((r) => { release = r; });
    vi.stubGlobal("fetch", vi.fn(async (u: string) => {
      if (u.startsWith("/api/handoffs?")) return Response.json({ data: [row("HND-A"), row("HND-B")] });
      if (u.endsWith("HND-A")) { await slowA; return Response.json({ data: { packet: packet("HND-A"), control: "agent" } }); }
      return Response.json({ data: { packet: packet("HND-B"), control: "agent" } });
    }));
    render(<Console me={me} initialId="HND-A" />);
    await userEvent.click(await screen.findByRole("option", { name: /HND-B/ }));
    expect(await screen.findByRole("heading", { name: /HND-B/ })).toBeInTheDocument();
    await act(async () => { release(); await slowA; });
    expect(screen.getByRole("heading", { name: /HND-B/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /HND-A/ })).toBeNull();
  });

  it("posts the action to the case on screen", async () => {
    const f = vi.fn(async (u: string, init?: RequestInit) => {
      if (u.startsWith("/api/handoffs?")) return Response.json({ data: [row("HND-A")] });
      if (init?.method === "POST") return Response.json({ data: packet("HND-A") });
      return Response.json({ data: { packet: packet("HND-A"), control: "agent" } });
    });
    vi.stubGlobal("fetch", f);
    render(<Console me={me} initialId="HND-A" />);
    await userEvent.click(await screen.findByRole("button", { name: "Claim" }));
    await waitFor(() => expect(f.mock.calls.some(([u, i]) => u === "/api/handoffs/HND-A/claim" && i?.method === "POST")).toBe(true));
  });

  it("does not reload the acted-on case over a newly selected one", async () => {
    let release!: () => void;
    const slow = new Promise<void>((r) => { release = r; });
    vi.stubGlobal("fetch", vi.fn(async (u: string, init?: RequestInit) => {
      if (u.startsWith("/api/handoffs?")) return Response.json({ data: [row("HND-A"), row("HND-B")] });
      if (init?.method === "POST") { await slow; return Response.json({ data: packet("HND-A") }); }
      return Response.json({ data: { packet: packet(u.endsWith("HND-A") ? "HND-A" : "HND-B"), control: "agent" } });
    }));
    render(<Console me={me} initialId="HND-A" />);
    await userEvent.click(await screen.findByRole("button", { name: "Claim" }));
    await userEvent.click(screen.getByRole("option", { name: /HND-B/ }));
    expect(await screen.findByRole("heading", { name: /HND-B/ })).toBeInTheDocument();
    await act(async () => { release(); await slow; });
    expect(screen.getByRole("heading", { name: /HND-B/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /HND-A/ })).toBeNull();
  });
});
