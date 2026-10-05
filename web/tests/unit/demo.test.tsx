// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DemoStage } from "@/components/demo/DemoStage";
import { ScenarioRail } from "@/components/demo/ScenarioRail";
import { SignInPanel } from "@/components/demo/SignInPanel";
import { SCENARIOS } from "@/lib/demo/scenarios";

vi.mock("@/components/trace/TraceList", () => ({ TraceList: () => null }));
vi.mock("@/components/demo/HandoffTicker", () => ({ HandoffTicker: () => null }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

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
      claimsAt={Date.now()} claims={{ sub: "CLI-0421", sid: "S-9f2c", lang: "es", scopes: ["dispute:create", "inquiry:read"], exp: Math.floor(Date.now() / 1000) + 900 }} />);
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

describe("ScenarioRail chips", () => {
  it("renders all eight scenario chips", () => {
    render(<ScenarioRail users={[]} onStart={vi.fn()} activeKey={null} nextStep={null} onPrefill={vi.fn()} />);
    expect(screen.getAllByRole("button")).toHaveLength(8);
  });
});

describe("DemoStage", () => {
  const post = vi.fn();
  const fromPhone = (data: object) => act(() => { window.dispatchEvent(new MessageEvent("message", { data, origin: window.location.origin })); });
  function setup() {
    post.mockClear();
    vi.spyOn(HTMLIFrameElement.prototype, "contentWindow", "get").mockReturnValue({ postMessage: post } as never);
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.includes("demo-users")
      ? { ok: true, json: async () => ({ data: [{ username: "ana.mx", lang: "es", scenarios: ["clarify", "dispute_filed"] }] }) }
      : { ok: true, json: async () => ({ data: { sub: "C", sid: "S1", lang: "es", scopes: ["inquiry:read"], exp: 0 } }) }));
    render(<DemoStage />);
  }
  const open = async (name: RegExp) => {
    await userEvent.click(screen.getByRole("button", { name: /3 · Scenarios/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: name })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: name }));
  };

  it("puts the first scripted message in the composer when the new session appears", async () => {
    setup();
    await open(/ambiguous/);
    expect(post).not.toHaveBeenCalled();
    fromPhone({ type: "demo:session", sid: "S1" });
    expect(post).toHaveBeenCalledWith({ type: "demo:prefill", text: "Tengo un problema con un pago" }, window.location.origin);
  });

  it("advances the script only for the scripted message", async () => {
    setup();
    await open(/dispute filed/);
    fromPhone({ type: "demo:session", sid: "S1" });
    fromPhone({ type: "demo:turn-start", text: "hola, una pregunta" });
    fromPhone({ type: "demo:turn-reply", turn_id: "T1" });
    expect(screen.queryByText("Next message")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Put in composer: Me cobraron/ })).toBeInTheDocument();
    fromPhone({ type: "demo:turn-start", text: "Me cobraron dos veces la misma compra, quiero reclamar el segundo cobro" });
    fromPhone({ type: "demo:turn-reply", turn_id: "T2" });
    expect(screen.getByRole("button", { name: "Put in composer: Confirmar y enviar" })).toBeInTheDocument();
  });

  it("marks realtime only when the phone's channel is live and says when a fetch fails", async () => {
    setup();
    fromPhone({ type: "demo:session", sid: "S1" });
    expect(screen.getByText("Realtime token issued").closest("li")).toHaveAttribute("data-done", "false");
    fromPhone({ type: "demo:realtime" });
    expect(screen.getByText("Realtime token issued").closest("li")).toHaveAttribute("data-done", "true");
    fromPhone({ type: "demo:auth", step: "token_issued" });
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false })));
    fromPhone({ type: "demo:auth", step: "token_issued" });
    expect(await screen.findByRole("alert")).toHaveTextContent(/claims/);
  });
});
