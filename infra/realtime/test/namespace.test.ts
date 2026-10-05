import { describe, expect, it, vi } from "vitest";
import { CASES } from "./rules.cases";

const unauthorized = vi.fn(() => { throw new Error("Unauthorized"); });
vi.mock("@aws-appsync/utils", () => ({ util: { unauthorized } }));

// eslint-disable-next-line @typescript-eslint/no-require-imports
const ns = await import("../handlers/namespace.js");

describe("namespace channel rules", () => {
  it.each(CASES)("%s", (_name, segments, c, ok) => {
    expect(ns.allowed(segments, c)).toBe(ok);
  });

  it("onSubscribe reads handlerContext or resolverContext and refuses others' channels", () => {
    const ctx = (identity: object, segments: string[]) => ({ identity, info: { channel: { segments, path: "/" + segments.join("/") } } });
    expect(() => ns.onSubscribe(ctx({ handlerContext: { role: "customer", sid: "S-1" } }, ["session", "S-1"]))).not.toThrow();
    expect(() => ns.onSubscribe(ctx({ resolverContext: { role: "customer", sid: "S-1" } }, ["session", "S-1"]))).not.toThrow();
    expect(() => ns.onSubscribe(ctx({ handlerContext: { role: "customer", sid: "S-1" } }, ["session", "S-2"]))).toThrow("Unauthorized");
    expect(() => ns.onSubscribe(ctx({}, ["queue", "all"]))).toThrow("Unauthorized");
  });

  it("onPublish refuses a Lambda-authorizer identity (browsers never publish)", () => {
    const events = [{ id: "1", payload: {} }];
    expect(() => ns.onPublish({ events, identity: { handlerContext: { role: "agent", sid: "x" } } })).toThrow("Unauthorized");
    expect(() => ns.onPublish({ events, identity: { resolverContext: { role: "agent", sid: "x" } } })).toThrow("Unauthorized");
  });

  it("onPublish forwards events unchanged", () => {
    const events = [{ id: "1", payload: { a: 1 } }];
    expect(ns.onPublish({ events })).toBe(events);
  });
});
