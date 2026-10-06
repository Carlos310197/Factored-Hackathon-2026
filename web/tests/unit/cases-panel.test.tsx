// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CasesPanel } from "@/components/customer/CasesPanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const stub = (data: unknown[]) => {
  const f = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data }), { status: 200 }));
  vi.stubGlobal("fetch", f);
  return f;
};

describe("CasesPanel", () => {
  it("opens a dialog, fetches and lists cases with friendly status, Escape closes and returns focus", async () => {
    const f = stub([{ dispute_id: "DSP-1759658400000A1B2C3D4", status: "pending_review", created_at: "2026-10-05T10:00:00+00:00",
      reason: "duplicate_charge", amount: 184900, currency: "COP" }]);
    render(<CasesPanel lang="es" />);
    const open = screen.getByRole("button", { name: "Mis casos" });
    await userEvent.click(open);
    expect(f).toHaveBeenCalledWith("/api/customer/cases", expect.anything());
    expect(screen.getByRole("dialog", { name: "Mis casos" })).toBeInTheDocument();
    expect(await screen.findByText("En revisión")).toBeInTheDocument();
    expect(screen.getByText("COP 184.900")).toBeInTheDocument();
    expect(screen.getByText("Cargo duplicado")).toBeInTheDocument();
    expect(screen.getByTitle("DSP-1759658400000A1B2C3D4")).toHaveTextContent("DSP-…A1B2C3D4");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(open).toHaveFocus();
  });
  it("shows the empty state in Portuguese and closes with the close button", async () => {
    stub([]);
    render(<CasesPanel lang="pt" />);
    await userEvent.click(screen.getByRole("button", { name: "Meus casos" }));
    expect(await screen.findByText("Você não tem casos abertos")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fechar" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
