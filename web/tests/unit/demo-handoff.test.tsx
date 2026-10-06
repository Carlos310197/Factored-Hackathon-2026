// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Console } from "@/components/staff/Console";
import { HandoffPanel } from "@/components/demo/HandoffPanel";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/lib/staff/redirect", () => ({ redirectToStaffLogin: vi.fn() }));
vi.mock("@/lib/realtime/useChannel", () => ({ useChannel: () => "polling" }));
vi.mock("@/components/staff/ConsoleWithTabs", () => ({
  ConsoleWithTabs: (p: { initialId?: string; caseOnly?: boolean }) => <p>{`console ${p.initialId} caseOnly=${p.caseOnly}`}</p>,
}));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

const me = { sub: "agent.ana", name: "Ana R." };
const T0 = "2026-10-05T21:00:00.000Z";
const row = (id: string, sid: string, status = "open", created_at = T0) =>
  ({ handoff_id: id, session_id: sid, status, priority: "critical", reason_codes: ["unauthorized_use"], language: "es", created_at });
const packet = (id: string, sid: string) => ({ schema_version: "handoff.v1", handoff_id: id, created_at: T0, status: "claimed", session_id: sid,
  claimed_by: "agent.ana", claimed_at: "2026-10-05T21:00:42.000Z", customer_id: "CLI-1", language: "es", data_as_of: "2026-06-17",
  priority: "critical", reason_codes: ["unauthorized_use"], customer_request: { original: "x", en: "x" }, verified_facts: [],
  actions_taken: [], decisions: [], policy_checks: [], open_questions: [], transcript_ref: "t" });
const turn = (ms: number, template = false) => ({ turnId: `t${ms}`, quote: "q", quoteEn: null, durationMs: ms, bars: [],
  folded: { count: 0, highest: null, bars: [] }, replyCheck: { text: "", failed: false, regenerated: template ? 1 : 0, template },
  errors: [], route: { next: "reply", priority: null, policy: [] }, versions: {} });

function api(lists: Record<string, object[]>, turns: object[] = []) {
  vi.stubGlobal("fetch", vi.fn(async (u: string) => {
    if (u.startsWith("/api/handoffs?filter=")) return Response.json({ data: lists[u.split("=")[1]] ?? [] });
    if (u.startsWith("/api/handoffs/")) { const id = u.split("/").pop()!; return Response.json({ data: { packet: packet(id, "S1"), control: "agent" } }); }
    if (u.startsWith("/api/trace/")) return Response.json({ data: turns });
    throw new Error(u);
  }));
}

describe("Console stats", () => {
  it("counts every queue filter on its chip and shows the oldest open case", async () => {
    vi.useFakeTimers({ now: Date.parse("2026-10-05T21:09:00.000Z"), toFake: ["Date"] });
    api({ open: [row("HND-A", "S9"), row("HND-B", "S8", "open", "2026-10-05T21:05:00.000Z")], mine: [row("HND-C", "S1", "claimed")],
      resolved: [row("HND-D", "S7", "resolved")] });
    render(<Console me={me} />);
    expect(await screen.findByRole("button", { name: "Open 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mine 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "In takeover 0" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resolved 1" })).toBeInTheDocument();
    expect(screen.getByText("oldest open 9 min")).toBeInTheDocument();
  });

  it("shows the conversation's numbers under the case header", async () => {
    api({ mine: [row("HND-C", "S1", "claimed")] }, [turn(3200), turn(4800, true)]);
    render(<Console me={me} initialId="HND-C" />);
    const stats = await screen.findByRole("list", { name: "Conversation stats" });
    await waitFor(() => expect(stats).toHaveTextContent("2 turns")); // the turn numbers arrive with the trace
    expect(stats).toHaveTextContent("mean reply 4.0 s");
    expect(stats).toHaveTextContent("1 template fallback");
    expect(stats).toHaveTextContent("claimed 42 s after handoff");
  });

  it("caseOnly shows the case without the queue or the console's own top bar", async () => {
    api({ open: [row("HND-A", "S1")] });
    render(<Console me={me} initialId="HND-A" caseOnly />);
    expect(await screen.findByRole("heading", { name: /HND-A/ })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Case queue" })).toBeNull();
    expect(screen.queryByText("LATAM Bank · Agent console")).toBeNull();
  });
});

describe("HandoffPanel", () => {
  it("asks for a conversation when the phone has no session", () => {
    api({});
    render(<HandoffPanel sid={null} me={me} refreshKey={0} />);
    expect(screen.getByText(/Sign in on the phone/)).toBeInTheDocument();
  });

  it("waits for a handoff while this session has none, even if other sessions do", async () => {
    api({ open: [row("HND-OTHER", "S9")] });
    render(<HandoffPanel sid="S1" me={me} refreshKey={0} />);
    expect(await screen.findByText(/No handoff yet for this conversation/)).toBeInTheDocument();
    expect(screen.queryByText(/console HND-OTHER/)).toBeNull();
  });

  it("opens this session's newest handoff in a case-only console under the as-is dispute line", async () => {
    api({ open: [row("HND-OLD", "S1", "open", "2026-10-05T20:00:00.000Z"), row("HND-OTHER", "S9")], mine: [row("HND-NEW", "S1", "claimed")] });
    render(<HandoffPanel sid="S1" me={me} refreshKey={0} />);
    expect(await screen.findByText("console HND-NEW caseOnly=true")).toBeInTheDocument();
    const line = screen.getByText(/Disputes today/).closest("p")!;
    expect(line).toHaveTextContent("37.0 h");
    expect(line).toHaveTextContent("15.5 d");
    expect(line).toHaveTextContent("69.8 %");
  });
});
