import { GetCommand, PutCommand } from "@aws-sdk/lib-dynamodb";
import { beforeAll, beforeEach, expect, it, describe } from "vitest";
import { createTables } from "../helpers/tables";

const endpoint = process.env.DYNAMODB_ENDPOINT;
const run = endpoint ? describe : describe.skip;

run("customer conversation sessions (DynamoDB)", () => {
  let s: typeof import("@/lib/server/sessions");
  let m: typeof import("@/lib/server/messages");
  let d: typeof import("@/lib/server/ddb");
  const put = (item: Record<string, unknown>) => d.doc().send(new PutCommand({ TableName: d.tableName("sessions"), Item: item }));
  const row = (sid: string, customer: string, created: string, over: Record<string, unknown> = {}) =>
    ({ session_id: sid, customer_id: customer, language: "es", control: "agent", created_at: created, ...over });

  beforeAll(async () => {
    process.env.TABLE_PREFIX = "webtest-sess";
    process.env.AWS_ACCESS_KEY_ID = "local";
    process.env.AWS_SECRET_ACCESS_KEY = "local";
    [s, m, d] = await Promise.all([import("@/lib/server/sessions"), import("@/lib/server/messages"), import("@/lib/server/ddb")]);
  });
  beforeEach(async () => { await createTables("webtest-sess", endpoint!); });

  it("lists only the customer's visible conversations, newest first, with the first customer message as preview", async () => {
    await put(row("S-OLD", "CLI-A", "2026-10-01T10:00:00.000000+00:00", { ended_at: "2026-10-01T10:05:00.000000+00:00" }));
    await put(row("S-NEW", "CLI-A", "2026-10-03T10:00:00.000000+00:00"));
    await put(row("S-HID", "CLI-A", "2026-10-02T10:00:00.000000+00:00", { hidden: true }));
    await put(row("S-ELSE", "CLI-B", "2026-10-04T10:00:00.000000+00:00"));
    await m.appendMessage("S-OLD", { role: "agent", text: "Hola, ¿en qué te ayudo?" });
    await m.appendMessage("S-OLD", { role: "customer", text: "No reconozco un cargo de $420 en Amazon, yo no hice esa compra y quiero que me devuelvan el dinero ya" });
    const list = await s.listCustomerSessions("CLI-A");
    expect(list.map((x) => x.session_id)).toEqual(["S-NEW", "S-OLD"]);
    expect(list[1]).toMatchObject({ ended: true, language: "es", created_at: "2026-10-01T10:00:00.000000+00:00" });
    expect(list[1].preview).toHaveLength(80);
    expect(list[1].preview!.startsWith("No reconozco un cargo")).toBe(true);
    expect(list[0]).toMatchObject({ ended: false, preview: null });
  });

  it("end creates the item for a conversation with no turns yet, marks it ended and refuses another customer's", async () => {
    const r = await s.endSession("S-FRESH", "CLI-A", "pt");
    expect(r.control).toBe("agent");
    const item = (await d.doc().send(new GetCommand({ TableName: d.tableName("sessions"), Key: { session_id: "S-FRESH" } }))).Item!;
    expect(item).toMatchObject({ customer_id: "CLI-A", language: "pt", control: "agent" });
    expect(item.ended_at).toEqual(expect.any(String));
    expect(item.created_at).toEqual(expect.any(String));
    expect(item.ttl).toEqual(expect.any(Number));
    await put(row("S-B", "CLI-B", "2026-10-04T10:00:00.000000+00:00"));
    await expect(s.endSession("S-B", "CLI-A", "es")).rejects.toBeInstanceOf(d.NotFoundError);
  });

  it("end keeps an existing conversation's fields and reports a human's control", async () => {
    await put(row("S-H", "CLI-A", "2026-10-01T10:00:00.000000+00:00", { control: "human:agent.ana", language: "es" }));
    const r = await s.endSession("S-H", "CLI-A", "pt");
    expect(r.control).toBe("human:agent.ana");
    const item = (await s.getSession("S-H"))!;
    expect(item).toMatchObject({ language: "es", created_at: "2026-10-01T10:00:00.000000+00:00" });
  });

  it("hide works only for the owner", async () => {
    await put(row("S-1", "CLI-A", "2026-10-01T10:00:00.000000+00:00"));
    await expect(s.hideSession("S-1", "CLI-B")).rejects.toBeInstanceOf(d.NotFoundError);
    await expect(s.hideSession("S-NOPE", "CLI-A")).rejects.toBeInstanceOf(d.NotFoundError);
    await s.hideSession("S-1", "CLI-A");
    expect(await s.listCustomerSessions("CLI-A")).toEqual([]);
  });
});
