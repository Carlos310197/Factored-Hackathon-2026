import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ staffFrom: vi.fn(), listRecords: vi.fn(), listMessages: vi.fn() }));
vi.mock("@/lib/server/session", () => ({ staffFrom: m.staffFrom }));
vi.mock("@/lib/server/records", () => ({ listRecords: m.listRecords }));
vi.mock("@/lib/server/messages", () => ({ listMessages: m.listMessages }));

const ctx = { params: Promise.resolve({ sid: "S-1" }) };
beforeEach(() => vi.resetAllMocks());

describe("GET /api/trace/[sid]", () => {
  it("is 401 without staff", async () => {
    m.staffFrom.mockResolvedValue(null);
    const { GET } = await import("@/app/api/trace/[sid]/route");
    expect((await GET(new NextRequest("http://localhost/api/trace/S-1"), ctx)).status).toBe(401);
    expect(m.listRecords).not.toHaveBeenCalled();
  });
  it("returns turns, passing ?turn= to the record query", async () => {
    m.staffFrom.mockResolvedValue({ sub: "agent.ana" });
    m.listRecords.mockResolvedValue([{ session_id: "S-1", sk: "T1#0001", turn_id: "T1", seq: 1, node: "understand", kind: "route", ts: "t",
      payload: { next: "clarify", reasons: [] }, versions: {} }]);
    m.listMessages.mockResolvedValue([]);
    const { GET } = await import("@/app/api/trace/[sid]/route");
    const res = await GET(new NextRequest("http://localhost/api/trace/S-1?turn=T1"), ctx);
    expect(m.listRecords).toHaveBeenCalledWith("S-1", "T1");
    expect((await res.json()).data[0]).toMatchObject({ turnId: "T1", route: { next: "clarify" } });
  });
});
