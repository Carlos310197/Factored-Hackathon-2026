// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CaseHeader } from "@/components/staff/CaseHeader";
import { allowedActions } from "@/lib/staff/actions";

afterEach(cleanup);

describe("allowedActions", () => {
  it.each([
    ["open", null, "agent.ana", ["claim"]],
    ["claimed", "agent.ana", "agent.ana", ["takeover", "resolve"]],
    ["claimed", "agent.luis", "agent.ana", []],
    ["in_takeover", "agent.ana", "agent.ana", ["return", "resolve"]],
    ["returned", "agent.ana", "agent.ana", ["takeover", "resolve"]],
    ["resolved", "agent.ana", "agent.ana", []],
  ] as const)("%s held by %s as %s → %j", (status, claimed_by, me, expected) => {
    expect(allowedActions({ status, claimed_by }, me)).toEqual(expected);
  });
});

describe("CaseHeader", () => {
  const packet = { handoff_id: "HND-7Q2K", status: "claimed", claimed_by: "agent.ana", priority: "critical", customer_id: "CLI-0421",
    language: "es", data_as_of: "2026-06-17", session_id: "S-9f2c", created_at: "2026-09-30T14:02:00Z" } as never;
  it("shows only allowed actions and names who holds the case", async () => {
    const onAction = vi.fn();
    render(<CaseHeader packet={packet} control="agent" me={{ sub: "agent.ana", name: "Ana R." }} onAction={onAction} />);
    expect(screen.getByRole("heading", { name: /HND-7Q2K/ })).toBeInTheDocument();
    expect(screen.getByText(/Critical · claimed/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Claim" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Take over chat" }));
    expect(onAction).toHaveBeenCalledWith("takeover", undefined);
  });
  it("resolve asks for an outcome and a note", async () => {
    const onAction = vi.fn();
    render(<CaseHeader packet={packet} control="agent" me={{ sub: "agent.ana", name: "Ana R." }} onAction={onAction} />);
    await userEvent.click(screen.getByRole("button", { name: "Resolve…" }));
    await userEvent.selectOptions(screen.getByLabelText("Outcome"), "no_action_needed");
    await userEvent.type(screen.getByLabelText("Note"), "Customer recognized the charge");
    await userEvent.click(screen.getByRole("button", { name: "Resolve case" }));
    expect(onAction).toHaveBeenCalledWith("resolve", { code: "no_action_needed", note: "Customer recognized the charge" });
  });
});