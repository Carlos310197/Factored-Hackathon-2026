// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ScenarioRail } from "@/components/demo/ScenarioRail";
import { SignInPanel } from "@/components/demo/SignInPanel";
import { SCENARIOS } from "@/lib/demo/scenarios";

afterEach(cleanup);

describe("SCENARIOS", () => {
  it("covers the eight definition-of-done cases with the tag names used by tag_scenarios.py", () => {
    expect(SCENARIOS.map((s) => s.key)).toEqual(["account_inquiry", "decline_explanation", "dispute_filed", "clarify", "abstain",
      "unauthorized_handoff", "injection_refused", "expired_token"]);
    expect(SCENARIOS.find((s) => s.key === "decline_explanation")?.lang).toBe("pt");
    expect(SCENARIOS.find((s) => s.key === "dispute_filed")?.steps).toHaveLength(2);
  });
});

describe("SignInPanel", () => {
  it("shows each step's state and the decoded claims as text", () => {
    render(<SignInPanel steps={{ otp: true, token: true, realtime: false, firstTurn: false }}
      claims={{ sub: "CLI-0421", sid: "S-9f2c", lang: "es", scopes: ["dispute:create", "inquiry:read"], exp: Math.floor(Date.now() / 1000) + 900 }} />);
    expect(screen.getByText("OTP verified").closest("li")).toHaveAttribute("data-done", "true");
    expect(screen.getByText("Realtime token issued").closest("li")).toHaveAttribute("data-done", "false");
    expect(screen.getByText("CLI-0421 (sub)")).toBeInTheDocument();
    expect(screen.getByText("inquiry:read · dispute:create")).toBeInTheDocument();
    expect(screen.getByText(/in 1[45] min/)).toBeInTheDocument();
  });
});

describe("ScenarioRail", () => {
  const users = [{ username: "ana.mx", lang: "es", scenarios: ["unauthorized_handoff", "clarify"] }];
  it("disables scenarios without a tagged identity and starts the others", async () => {
    const onStart = vi.fn();
    render(<ScenarioRail users={users} onStart={onStart} activeKey={null} nextStep={null} onPrefill={vi.fn()} />);
    expect(screen.getByRole("button", { name: /dispute filed/i })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /unauthorized → handoff/i }));
    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ key: "unauthorized_handoff" }), "ana.mx");
  });
  it("offers the next scripted message as a chip", async () => {
    const onPrefill = vi.fn();
    render(<ScenarioRail users={users} onStart={vi.fn()} activeKey="clarify" nextStep="Tengo un problema con un pago" onPrefill={onPrefill} />);
    await userEvent.click(screen.getByRole("button", { name: "Put in composer: Tengo un problema con un pago" }));
    expect(onPrefill).toHaveBeenCalledWith("Tengo un problema con un pago");
  });
});
