import { marshall } from "@aws-sdk/util-dynamodb";
import { describe, expect, it, vi } from "vitest";
import { makeHandler } from "../publisher/index";
import { publish } from "../publisher/publish";

const signer = { sign: vi.fn(async (req: { headers: Record<string, string> }) => ({ ...req, headers: { ...req.headers, authorization: "SIG" } })) };

describe("publish", () => {
  it("posts at most 5 events per request with stringified payloads", async () => {
    const calls: Array<{ url: string; body: { channel: string; events: string[] } }> = [];
    const fetchImpl = vi.fn(async (url: string, init: { body: string }) => {
      calls.push({ url, body: JSON.parse(init.body) });
      return new Response(JSON.stringify({ successful: [], failed: [] }), { status: 200 });
    });
    await publish("/trace/S-1", Array.from({ length: 7 }, (_, i) => ({ type: "record", seq: i })),
      { httpDomain: "abc.appsync-api.us-east-2.amazonaws.com", signer, fetchImpl: fetchImpl as unknown as typeof fetch });
    expect(calls.map((c) => c.body.events.length)).toEqual([5, 2]);
    expect(calls[0].url).toBe("https://abc.appsync-api.us-east-2.amazonaws.com/event");
    expect(JSON.parse(calls[0].body.events[0])).toEqual({ type: "record", seq: 0 });
  });
  it("throws on HTTP errors and on per-event failures", async () => {
    const deps = (res: Response) => ({ httpDomain: "h", signer, fetchImpl: (async () => res) as unknown as typeof fetch });
    await expect(publish("/x/y", [{ a: 1 }], deps(new Response("no", { status: 403 })))).rejects.toThrow("403");
    await expect(publish("/x/y", [{ a: 1 }], deps(new Response(JSON.stringify({ failed: [{ identifier: "0" }] }), { status: 200 })))).rejects.toThrow("failed");
  });
});

describe("handler", () => {
  const rec = (seq: string, table: string, image: Record<string, unknown>) => ({
    eventName: "INSERT", eventSourceARN: `arn:aws:dynamodb:us-east-2:1:table/p-${table}/stream/1`,
    dynamodb: { SequenceNumber: seq, NewImage: marshall(image) } });

  it("reports only the failing record and still publishes the others", async () => {
    const sent: string[] = [];
    const handler = makeHandler(async (channel) => {
      if (channel === "/session/BAD") throw new Error("boom");
      sent.push(channel);
    });
    const out = await handler({ Records: [
      rec("1", "conversation_messages", { session_id: "S-1", sk: "a#1", kind: "message", message_id: "1", role: "customer", text: "hi", ts: "t" }),
      rec("2", "conversation_messages", { session_id: "BAD", sk: "a#2", kind: "message", message_id: "2", role: "customer", text: "x", ts: "t" }),
      rec("3", "handoffs", { handoff_id: "H", session_id: "S-1", status: "open", priority: "high", reason_codes: [], language: "es", created_at: "c" }),
    ] } as never);
    expect(out.batchItemFailures).toEqual([{ itemIdentifier: "2" }]);
    expect(sent).toEqual(["/session/S-1", "/queue/all"]);
  });
});
