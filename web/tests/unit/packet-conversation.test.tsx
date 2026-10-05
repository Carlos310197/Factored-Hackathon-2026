// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationTab } from "@/components/staff/ConversationTab";
import { HandoffPacket } from "@/lib/contract";
import { PacketTab, whyBars } from "@/components/staff/PacketTab";

vi.mock("@/lib/realtime/useChannel", () => ({ useChannel: () => "polling" }));
vi.mock("@/lib/chat/api", () => {
  const messages = [
    { id: "1", cursor: "1", role: "customer", text: "No reconozco", ts: "t" },
    { id: "2", cursor: "2", role: "system", text: "x", ts: "t", meta: { control: "human:agent.ana", agent_name: "Ana R." } },
  ];
  return { syncHistory: async (store: { getState(): { merge(m: unknown[]): void } }) => store.getState().merge(messages) };
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const PACKET = { schema_version: "handoff.v1", handoff_id: "HND-1", created_at: "c", status: "claimed", session_id: "S-1", customer_id: "CLI-1",
  language: "es", data_as_of: "2026-06-17", priority: "critical", reason_codes: [], transcript_ref: "session:S-1",
  customer_request: { original: "No reconozco un cargo de $420", en: "I don't recognize a $420 charge" },
  verified_facts: [{ fact: "Amazon · USD 420.00 · Approved", receipt_id: "r-114" }],
  actions_taken: [{ action: "dispute_drafted", result: "pending_review", receipt_id: "r-117" }], decisions: [],
  policy_checks: [{ rule: "within_60_days", passed: true }, { rule: "fraud_score_ok", passed: false }],
  open_questions: ["¿Todavía tiene la tarjeta?"] } as never;
const BAR = { signal: "reports_unauthorized_use", label: "Reports unauthorized use", value: 0.88, threshold: 0.5, crossed: true,
  color: "#e87ba4", verdict: { icon: "⚑", text: "handoff" } } as const;
const me = { sub: "agent.ana", name: "Ana R." };

describe("PacketTab", () => {
  it("shows request, facts with receipts, failed policy first, open questions and why", () => {
    render(<PacketTab packet={PACKET} why={[BAR]} />);
    expect(screen.getByText(/No reconozco un cargo de \$420/)).toBeInTheDocument();
    expect(screen.getByText("EN: I don't recognize a $420 charge")).toBeInTheDocument();
    expect(screen.getByText("rcpt r-114")).toBeInTheDocument();
    const checks = screen.getAllByTestId("policy-check");
    expect(checks[0]).toHaveTextContent("fraud score ok");
    expect(checks[0]).toHaveTextContent("fail");
    expect(screen.getByText("¿Todavía tiene la tarjeta?")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Reports unauthorized use" })).toHaveAttribute("aria-valuenow", "0.88");
  });
  it("whyBars takes the crossed bars of the handoff turn", () => {
    const turns = [{ route: { next: "answer_inquiry" }, bars: [BAR] },
      { route: { next: "handoff" }, bars: [BAR, { ...BAR, signal: "intent", crossed: true }, { ...BAR, signal: "distress", crossed: false }] }] as never;
    expect(whyBars(turns).map((b) => b.signal)).toEqual(["reports_unauthorized_use", "intent"]);
  });
});

describe("ConversationTab", () => {
  it("disables the composer unless this agent holds the takeover", async () => {
    const { rerender } = render(<ConversationTab sid="S-1" lang="es" control="agent" me={me} />);
    expect(await screen.findByText("No reconozco")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeDisabled();
    expect(screen.queryByText("Write in Spanish")).toBeNull();
    rerender(<ConversationTab sid="S-1" lang="es" control="human:agent.ana" me={me} />);
    expect(screen.getByRole("textbox")).toBeEnabled();
    expect(screen.getByText("Write in Spanish")).toBeInTheDocument();
    rerender(<ConversationTab sid="S-1" lang="es" control="human:agent.bob" me={me} />);
    expect(screen.getByRole("textbox")).toBeDisabled();
  });
  it("posts the message and clears the box; a 409 shows the lost-takeover message", async () => {
    const f = vi.fn(async () => new Response("{}", { status: 201 }));
    vi.stubGlobal("fetch", f);
    render(<ConversationTab sid="S-1" lang="es" control="human:agent.ana" me={me} />);
    await userEvent.type(screen.getByRole("textbox"), "Hola");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByRole("textbox")).toHaveValue(""));
    expect(f).toHaveBeenCalledWith("/api/sessions/S-1/messages", expect.objectContaining({ method: "POST", body: JSON.stringify({ text: "Hola" }) }));
    f.mockImplementation(async () => new Response("{}", { status: 409 }));
    await userEvent.type(screen.getByRole("textbox"), "Otra");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("You no longer hold this conversation.");
  });
});

describe("PacketTab without receipts", () => {
  it("parses and renders an action with a null receipt id", () => {
    const p = HandoffPacket.parse({ ...(PACKET as object), actions_taken: [{ action: "escalated", result: "ok", receipt_id: null }] });
    render(<PacketTab packet={p} why={[]} />);
    expect(screen.getByText("escalated · ok")).toBeInTheDocument();
    expect(screen.queryByText(/rcpt null/)).toBeNull();
  });
});
