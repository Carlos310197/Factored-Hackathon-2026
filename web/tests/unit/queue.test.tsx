// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Queue } from "@/components/staff/Queue";

const rows = [
  { handoff_id: "HND-7Q2K", session_id: "S", status: "claimed", priority: "critical", reason_codes: ["reports_unauthorized_use"], language: "es", created_at: new Date(Date.now() - 120_000).toISOString(), claimed_by: "agent.ana" },
  { handoff_id: "HND-7PZZ", session_id: "S2", status: "open", priority: "medium", reason_codes: ["asks_for_human"], language: "pt", created_at: new Date(Date.now() - 840_000).toISOString() },
] as never;

afterEach(cleanup);

describe("Queue", () => {
  it("renders priority as a word, plain reasons, language, age and holder", () => {
    render(<Queue rows={rows} filter="open" onFilter={vi.fn()} selected="HND-7Q2K" onSelect={vi.fn()} fresh={new Set(["HND-7PZZ"])} me="agent.ana" />);
    const first = screen.getAllByRole("option")[0];
    expect(within(first).getByText("HND-7Q2K")).toBeInTheDocument();
    expect(first).toHaveTextContent("Critical · Unauthorized use · ES · held by you");
    expect(first).toHaveAttribute("aria-selected", "true");
    expect(screen.getAllByRole("option")[1]).toHaveTextContent("Medium · Asked for a person · PT");
  });
});