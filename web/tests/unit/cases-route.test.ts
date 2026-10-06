import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ customerFrom: vi.fn(), send: vi.fn() }));
vi.mock("@/lib/server/session", () => ({ customerFrom: m.customerFrom }));
vi.mock("@/lib/server/ddb", () => ({ doc: () => ({ send: m.send }), tableName: (n: string) => `lb-test-${n}` }));

const get = () => new NextRequest("http://localhost/api/customer/cases?customer_id=CLI-EVIL");
const ITEM = { dispute_id: "DSP-1", transaction_id: "TXN-1", customer_id: "CLI-A", product_id: "P", reason: "duplicate_charge",
  amount: 184900, currency: "COP", amount_usd: 44.1, customer_statement: { text: "secret" }, route: "automated",
  status: "submitted", policy_version: "v1", session_id: "S-1", turn_id: "T", language: "es", created_at: "2026-10-05T10:00:00+00:00" };

beforeEach(() => { vi.resetAllMocks(); m.send.mockResolvedValue({ Items: [ITEM] }); });

describe("GET /api/customer/cases", () => {
  it("is 401 without a customer session", async () => {
    m.customerFrom.mockResolvedValue(null);
    const { GET } = await import("@/app/api/customer/cases/route");
    expect((await GET(get())).status).toBe(401);
    expect(m.send).not.toHaveBeenCalled();
  });
  it("queries the by_customer GSI with the token's customer id, newest first", async () => {
    m.customerFrom.mockResolvedValue({ sub: "CLI-A", sid: "S-1" });
    const { GET } = await import("@/app/api/customer/cases/route");
    await GET(get());
    const input = m.send.mock.calls[0][0].input;
    expect(input).toMatchObject({ TableName: "lb-test-disputes", IndexName: "by_customer", ScanIndexForward: false, Limit: 20,
      ExpressionAttributeValues: { ":c": "CLI-A" } });
  });
  it("returns only the public shape", async () => {
    m.customerFrom.mockResolvedValue({ sub: "CLI-A", sid: "S-1" });
    const { GET } = await import("@/app/api/customer/cases/route");
    const body = await (await GET(get())).json();
    expect(body.data).toEqual([{ dispute_id: "DSP-1", status: "submitted", created_at: "2026-10-05T10:00:00+00:00",
      reason: "duplicate_charge", amount: 184900, currency: "COP" }]);
  });
});
