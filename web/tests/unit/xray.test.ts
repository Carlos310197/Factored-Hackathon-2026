import { describe, expect, it } from "vitest";
import type { DecisionRecord } from "@/lib/server/records";
import { buildTrace } from "@/lib/trace/viewModel";
import { xrayTraceUrl } from "@/lib/trace/xray";

const TID = "1-6720f2a0-0123456789abcdef01234567";
const rec = (seq: number, kind: string, extra: Partial<DecisionRecord> = {}): DecisionRecord => ({
  session_id: "S-1", sk: `T1#000${seq}`, turn_id: "T1", seq, node: kind === "turn_end" ? "turn" : "understand", kind,
  ts: `2026-10-01T00:00:0${seq}Z`,
  payload: kind === "turn_end" ? { duration_ms: 900, awaiting: "none" } : { next: "reply", reasons: [], goal: {} },
  versions: {}, ...extra,
});

describe("xrayTraceUrl", () => {
  it("builds the CloudWatch X-Ray console link", () => {
    expect(xrayTraceUrl(TID)).toBe(
      `https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#xray:traces/${TID}`);
  });
  it("rejects anything that isn't an X-Ray trace id", () => {
    expect(xrayTraceUrl("javascript:alert(1)")).toBeNull();
    expect(xrayTraceUrl("1-xyz-123")).toBeNull();
  });
});

describe("buildTrace trace link", () => {
  it("links a turn when one of its records carries trace_id", () => {
    const [turn] = buildTrace([rec(1, "route", { trace_id: TID }), rec(2, "turn_end")], []);
    expect(turn.traceUrl).toBe(xrayTraceUrl(TID));
  });
  it("has no link without trace_id", () => {
    expect(buildTrace([rec(1, "route"), rec(2, "turn_end")], [])[0].traceUrl).toBeUndefined();
  });
});
