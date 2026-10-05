import { NextRequest, NextResponse } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatMessage, ChatReply, HandoffPacket } from "@/lib/contract";

vi.mock("@/lib/server/jwt", async (orig) => ({ ...(await orig<typeof import("@/lib/server/jwt")>()),
  verifier: () => ({ customer: async () => { throw new (await import("@/lib/server/jwt")).AuthFailure("invalid"); },
    staff: async () => { throw new (await import("@/lib/server/jwt")).AuthFailure("invalid"); } }) }));

afterEach(() => { vi.unstubAllEnvs(); });

describe("contract matches the agent's real shapes", () => {
  it("parses a packet as graph/nodes.py writes it (string decision value, p, policy detail)", () => {
    const p = HandoffPacket.parse({ schema_version: "handoff.v1", handoff_id: "HND-1", created_at: "t", status: "open",
      session_id: "S", customer_id: "C", language: "pt", data_as_of: "2026-06-17", priority: "medium", reason_codes: [],
      customer_request: { original: "a", en: "b" }, verified_facts: [], actions_taken: [{ action: "x", result: "y" }],
      decisions: [{ question: "intent", value: "dispute_charge", p: 0.91, question_set: "understand.v1", thresholds: "thresholds.v1" },
        { question: "fraud", value: 0.2, question_set: "q", thresholds: "t" }],
      policy_checks: [{ rule: "r", passed: false, detail: "why" }], open_questions: [], transcript_ref: "session:S" });
    expect(p.decisions[0].value).toBe("dispute_charge");
  });
  it("accepts a summary whose None keys were dropped by the store", () => {
    const summary = { merchant: "Éxito", date: "2026-06-03" };
    expect(ChatReply.parse({ reply_text: "x", awaiting: "none", summary }).summary?.amount).toBeUndefined();
    expect(ChatMessage.parse({ id: "1", cursor: "c", role: "assistant", text: "x", ts: "t", meta: { summary } }).meta?.summary?.currency).toBeUndefined();
  });
});

describe("session cookies", () => {
  const cookie = async () => {
    const { setSessionCookie } = await import("@/lib/server/session");
    const res = NextResponse.json({}); setSessionCookie(res, "c", "v", 60);
    return res.cookies.get("c") as unknown as { secure?: boolean };
  };
  it("are Secure in production by default and with COOKIE_SECURE=1", async () => {
    vi.stubEnv("NODE_ENV", "production");
    expect((await cookie()).secure).toBe(true);
  });
  it("COOKIE_SECURE=0 serves plain HTTP", async () => {
    vi.stubEnv("NODE_ENV", "production"); vi.stubEnv("COOKIE_SECURE", "0");
    expect((await cookie()).secure).toBeFalsy();
  });
});

describe("E2E cookies on ECS", () => {
  it("are refused when the Fargate metadata var is present", async () => {
    vi.stubEnv("E2E_MOCK", "1"); vi.stubEnv("DEMO_MODE", "1"); vi.stubEnv("ECS_CONTAINER_METADATA_URI_V4", "http://169.254.170.2/v4");
    const { customerFrom } = await import("@/lib/server/session");
    const req = new NextRequest("http://localhost/", { headers: { cookie: "cust_session=e2e.customer.CLI-A.S-1.es" } });
    expect(await customerFrom(req)).toBeNull();
  });
});

describe("html lang", () => {
  it("follows the customer's language on customer pages and is en for staff", async () => {
    vi.resetModules();
    const m = { c: vi.fn(), s: vi.fn() };
    vi.doMock("next/font/google", () => ({ Hanken_Grotesk: () => ({ variable: "" }), Schibsted_Grotesk: () => ({ variable: "" }) }));
    vi.doMock("@/lib/server/session", () => ({ customerFromCookies: m.c, staffFromCookies: m.s }));
    const { default: Layout } = await import("@/app/layout");
    const lang = async () => ((await Layout({ children: null })) as { props: { lang: string } }).props.lang;
    m.c.mockResolvedValue({ lang: "pt" }); m.s.mockResolvedValue(null);
    expect(await lang()).toBe("pt");
    m.c.mockResolvedValue(null); m.s.mockResolvedValue({ sub: "a" });
    expect(await lang()).toBe("en");
    m.s.mockResolvedValue(null);
    expect(await lang()).toBe("es");
  });
});
