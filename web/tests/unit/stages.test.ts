import { describe, expect, it } from "vitest";
import { stageOf } from "@/lib/trace/stages";

describe("stageOf", () => {
  it.each([
    ["load_context", "tool", "understand"], ["understand", "llm", "understand"], ["understand", "jev", "understand"],
    ["understand", "model", "understand"], ["understand", "route", "decide"], ["check_eligibility", "policy", "act"],
    ["file_dispute", "tool", "act"], ["handoff", "tool", "act"], ["reply", "llm", "verify"], ["reply", "jev", "verify"],
    ["turn", "turn_end", null],
  ])("%s/%s → %s", (node, kind, stage) => expect(stageOf(node, kind)).toBe(stage));
});
