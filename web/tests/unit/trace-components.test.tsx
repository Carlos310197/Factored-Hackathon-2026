// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalysingCard } from "@/components/trace/AnalysingCard";
import { TraceList } from "@/components/trace/TraceList";
import { TraceTurnView } from "@/components/trace/TraceTurn";
import type { TraceBar, TraceTurn } from "@/lib/trace/viewModel";

let push: (p: unknown) => void = () => {};
vi.mock("@/lib/realtime/useChannel", () => ({ useChannel: (_c: string, on: (p: unknown) => void) => { push = on; return "live"; } }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const bar = (signal: string, value: number, threshold: number, crossed: boolean, verdict: TraceBar["verdict"], color = "#e87ba4"): TraceBar =>
  ({ signal, label: signal, value, threshold, crossed, color, verdict });
const TURN: TraceTurn = {
  turnId: "T2", quote: "No reconozco un cargo de $420 en Amazon", quoteEn: "I don't recognize…", durationMs: 2400,
  bars: [bar("reports_unauthorized_use", 0.88, 0.5, true, { icon: "⚑", text: "handoff" }),
    bar("intent", 0.93, 0.8, true, { icon: "✓", text: "act" }, "#2a78d6")],
  folded: { count: 2, highest: { label: "Distress", value: 0.11 }, bars: [bar("distress", 0.11, 0.6, false, { icon: "·", text: "no effect" }, "#a7b1be"),
    bar("asks_for_human", 0.06, 0.6, false, { icon: "·", text: "no effect" }, "#a7b1be")] },
  replyCheck: { text: "Reply check 2/2 claims supported · no unverified promises", failed: false, regenerated: 0, template: false },
  errors: ["Resolver failed → Jev alone"],
  route: { next: "handoff", priority: "critical", policy: [{ name: "fraud_score_ok", passed: false }, { name: "within_60_days", passed: true }] },
  versions: { questionSet: "understand.v1", thresholds: "thresholds.v1" },
};

describe("TraceTurnView", () => {
  it("renders open bars with verdicts, the fold, the reply check, errors and the route strip", () => {
    render(<TraceTurnView turn={TURN} />);
    expect(screen.getAllByRole("meter")).toHaveLength(2);
    expect(screen.getByText("⚑ handoff")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /2 more signals below threshold · highest Distress 0.11/ })).toBeInTheDocument();
    expect(screen.getByText(/Reply check 2\/2/)).toBeInTheDocument();
    expect(screen.getByText("Resolver failed → Jev alone")).toBeInTheDocument();
    expect(screen.getByText("Route: handoff · critical")).toBeInTheDocument();
    expect(screen.getByText(/fraud score ok ✗/)).toBeInTheDocument();
  });
  it("expands the folded signals on demand", async () => {
    render(<TraceTurnView turn={TURN} />);
    await userEvent.click(screen.getByRole("button", { name: /2 more signals/ }));
    expect(screen.getAllByRole("meter")).toHaveLength(4);
  });
  it("collapsed shows only the route strip", () => {
    render(<TraceTurnView turn={TURN} collapsed />);
    expect(screen.queryAllByRole("meter")).toHaveLength(0);
    expect(screen.getByText("Route: handoff · critical")).toBeInTheDocument();
  });
  it("lists failed policies first", () => {
    const t = { ...TURN, route: { ...TURN.route, policy: [{ name: "a_ok", passed: true }, { name: "b_ok", passed: false }] } };
    render(<TraceTurnView turn={t} />);
    expect(screen.getByText(/Policy: b ok ✗ · a ok ✓/)).toBeInTheDocument();
  });
});

describe("AnalysingCard", () => {
  it("marks finished, current and pending stages", () => {
    render(<AnalysingCard turnNumber={2} lit={["understand"]} current="decide" />);
    expect(screen.getByText("Analysing turn 2…")).toBeInTheDocument();
    expect(screen.getByText("Understand")).toHaveAttribute("data-state", "done");
    expect(screen.getByText("Decide")).toHaveAttribute("data-state", "now");
    expect(screen.getByText("Act")).toHaveAttribute("data-state", "pending");
  });
});

describe("TraceList", () => {
  it("lights stages from record events, then fetches and reveals the newest turn on turn_complete", async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({ data: fetchMock.mock.calls.length > 1 ? [TURN] : [] }) }));
    vi.stubGlobal("fetch", fetchMock);
    render(<TraceList sid="S1" mode="console" />);
    await waitFor(() => expect(screen.getByText(/No turns yet/)).toBeInTheDocument());
    act(() => push({ type: "record", turn_id: "T2", seq: 1, node: "understand", kind: "jev" }));
    expect(screen.getByText("Understand")).toHaveAttribute("data-state", "now");
    act(() => push({ type: "turn_complete", turn_id: "T2" }));
    await waitFor(() => expect(screen.getByText("Route: handoff · critical")).toBeInTheDocument());
    expect(screen.queryByText("Analysing turn 1…")).toBeNull();
    expect(fetchMock).toHaveBeenLastCalledWith("/api/trace/S1", { cache: "no-store" });
  });
});

describe("TraceList lifecycle", () => {
  it("drops a stale response after the sid changes", async () => {
    let resolveA: (v: unknown) => void = () => {};
    const fetchMock = vi.fn((url: string) => url.endsWith("/A")
      ? new Promise((res) => { resolveA = res; })
      : Promise.resolve({ ok: true, json: async () => ({ data: [] }) }));
    vi.stubGlobal("fetch", fetchMock);
    const { rerender } = render(<TraceList sid="A" mode="console" />);
    rerender(<TraceList sid="B" mode="console" />);
    await act(async () => { resolveA({ ok: true, json: async () => ({ data: [TURN] }) }); });
    expect(screen.queryByText("Route: handoff · critical")).toBeNull();
  });
  it("reveals the newest turn once, then clears the highlight", async () => {
    vi.useFakeTimers();
    try {
      vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ data: [TURN] }) })));
      const { container } = render(<TraceList sid="S1" mode="console" refreshKey={1} />);
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      expect(container.querySelector("article")?.className).toContain("ring-c-signal");
      await act(async () => { await vi.advanceTimersByTimeAsync(1600); });
      expect(container.querySelector("article")?.className).not.toContain("ring-c-signal");
    } finally { vi.useRealTimers(); }
  });
});

describe("reply check", () => {
  it("is collapsed on failure and expands on click", async () => {
    const t = { ...TURN, replyCheck: { ...TURN.replyCheck!, failed: true } };
    render(<TraceTurnView turn={t} />);
    const b = screen.getByRole("button", { name: /Reply check/ });
    expect(b).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(b);
    expect(b).toHaveAttribute("aria-expanded", "true");
  });
});
