import { GetCommand, PutCommand } from "@aws-sdk/lib-dynamodb";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createTables } from "../helpers/tables";

const endpoint = process.env.DYNAMODB_ENDPOINT;
const run = endpoint ? describe : describe.skip;
if (!endpoint) console.warn("ddb.test.ts skipped: set DYNAMODB_ENDPOINT (docker compose up -d dynamodb in agent/)");

const PACKET = (id: string, over: Record<string, unknown> = {}) => ({
  schema_version: "handoff.v1", handoff_id: id, created_at: "2026-09-30T10:00:00Z", status: "open", session_id: "S-1",
  customer_id: "CLI-A", language: "es", data_as_of: "2026-06-17", priority: "critical", reason_codes: ["reports_unauthorized_use"],
  customer_request: { original: "No reconozco", en: "I don't recognize" }, verified_facts: [], actions_taken: [],
  decisions: [], policy_checks: [], open_questions: [], transcript_ref: "session:S-1", ...over });

run("DynamoDB access", () => {
  let m: typeof import("@/lib/server/messages");
  let h: typeof import("@/lib/server/handoffs");
  let s: typeof import("@/lib/server/sessions");
  let r: typeof import("@/lib/server/records");
  let d: typeof import("@/lib/server/ddb");

  beforeAll(async () => {
    process.env.TABLE_PREFIX = "webtest";
    process.env.AWS_ACCESS_KEY_ID = "local";
    process.env.AWS_SECRET_ACCESS_KEY = "local";
    [m, h, s, r, d] = await Promise.all([import("@/lib/server/messages"), import("@/lib/server/handoffs"),
      import("@/lib/server/sessions"), import("@/lib/server/records"), import("@/lib/server/ddb")]);
  });
  beforeEach(async () => {
    await createTables("webtest", endpoint!);
    await d.doc().send(new PutCommand({ TableName: d.tableName("sessions"),
      Item: { session_id: "S-1", customer_id: "CLI-A", language: "es", control: "agent" } }));
  });

  it("appends and lists messages in order, after a cursor, skipping idempotency markers", async () => {
    const a = await m.appendMessage("S-1", { role: "customer", text: "hola", id: "cm-1" });
    expect(await m.claimMessageId("S-1", "cm-2")).toBe(true);
    expect(await m.claimMessageId("S-1", "cm-2")).toBe(false);
    const b = await m.appendMessage("S-1", { role: "agent", text: "Soy Ana", author: "Ana R." });
    expect((await m.listMessages("S-1")).map((x) => x.id)).toEqual(["cm-1", b.id]);
    expect((await m.listMessages("S-1", a.cursor)).map((x) => x.id)).toEqual([b.id]);
  });

  it("lists the queue by priority then age", async () => {
    for (const [id, p, t] of [["H1", "medium", "2026-09-30T09:00:00Z"], ["H2", "critical", "2026-09-30T10:00:00Z"],
      ["H3", "critical", "2026-09-30T08:00:00Z"]] as const) {
      await d.doc().send(new PutCommand({ TableName: d.tableName("handoffs"), Item: PACKET(id, { priority: p, created_at: t }) }));
    }
    expect((await h.listHandoffs(["open"])).map((x) => x.handoff_id)).toEqual(["H3", "H2", "H1"]);
  });

  it("claim is atomic: the second agent gets a conflict", async () => {
    await d.doc().send(new PutCommand({ TableName: d.tableName("handoffs"), Item: PACKET("H1") }));
    const rs = await Promise.allSettled([h.claim("H1", "agent.ana"), h.claim("H1", "agent.luis")]);
    expect(rs.filter((x) => x.status === "fulfilled")).toHaveLength(1);
    const lost = rs.find((x) => x.status === "rejected") as PromiseRejectedResult;
    expect(lost.reason).toBeInstanceOf(d.ConflictError);
    await expect(h.getHandoff("nope")).resolves.toBeNull();
    await expect(h.takeover("nope", "agent.ana", "Ana")).rejects.toBeInstanceOf(d.NotFoundError);
  });

  it("takeover sets control and writes a system message; return by a non-holder is 409 and control is unchanged", async () => {
    await d.doc().send(new PutCommand({ TableName: d.tableName("handoffs"), Item: PACKET("H1") }));
    await h.claim("H1", "agent.ana");
    const p = await h.takeover("H1", "agent.ana", "Ana R.");
    expect(p.status).toBe("in_takeover");
    expect((await s.getSession("S-1"))?.control).toBe("human:agent.ana");
    const sys = (await m.listMessages("S-1")).at(-1);
    expect(sys?.role).toBe("system");
    expect(sys?.meta?.control).toBe("human:agent.ana");
    await expect(h.returnToAssistant("H1", "agent.luis")).rejects.toBeInstanceOf(d.ConflictError);
    expect((await s.getSession("S-1"))?.control).toBe("human:agent.ana");
    expect((await h.returnToAssistant("H1", "agent.ana")).status).toBe("returned");
    expect((await s.getSession("S-1"))?.control).toBe("agent");
  });

  it("resolve needs the holder, records the resolution and hands control back", async () => {
    await d.doc().send(new PutCommand({ TableName: d.tableName("handoffs"), Item: PACKET("H1") }));
    await h.claim("H1", "agent.ana");
    await h.takeover("H1", "agent.ana", "Ana R.");
    await expect(h.resolve("H1", "agent.luis", "no_action_needed", "")).rejects.toBeInstanceOf(d.ConflictError);
    const p = await h.resolve("H1", "agent.ana", "resolved_by_agent", "Card blocked by phone");
    expect(p.status).toBe("resolved");
    expect(p.resolution?.code).toBe("resolved_by_agent");
    expect((await s.getSession("S-1"))?.control).toBe("agent");
  });

  it("resolve on a stale read conflicts and leaves control unchanged", async () => {
    await d.doc().send(new PutCommand({ TableName: d.tableName("handoffs"), Item: PACKET("H1") }));
    await h.claim("H1", "agent.ana");
    const client = d.doc();
    const orig = client.send.bind(client) as (c: unknown) => Promise<unknown>;
    let armed = true;
    const spy = vi.spyOn(client, "send").mockImplementation((async (cmd: unknown) => {
      const out = await orig(cmd);
      if (armed && cmd instanceof GetCommand) { // resolve has read status=claimed; a takeover lands before its write
        armed = false;
        await h.takeover("H1", "agent.ana", "Ana R.");
      }
      return out;
    }) as never);
    await expect(h.resolve("H1", "agent.ana", "resolved_by_agent", "x")).rejects.toBeInstanceOf(d.ConflictError);
    spy.mockRestore();
    expect((await s.getSession("S-1"))?.control).toBe("human:agent.ana");
    expect((await h.getHandoff("H1"))?.status).toBe("in_takeover");
  });

  it("lists decision records for a turn", async () => {
    for (const [sk, kind] of [["TRN-1#0001", "llm"], ["TRN-1#0002", "jev"], ["TRN-2#0001", "llm"]]) {
      await d.doc().send(new PutCommand({ TableName: d.tableName("decision_records"), Item: { session_id: "S-1", sk,
        turn_id: sk.split("#")[0], seq: Number(sk.split("#")[1]), node: "understand", kind, ts: "t", payload: {}, versions: {} } }));
    }
    expect((await r.listRecords("S-1", "TRN-1")).map((x) => x.kind)).toEqual(["llm", "jev"]);
    expect(await r.listRecords("S-1")).toHaveLength(3);
  });
});
