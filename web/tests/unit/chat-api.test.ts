import { afterEach, describe, expect, it, vi } from "vitest";
import { api, syncHistory } from "@/lib/chat/api";
import { createChatStore } from "@/lib/chat/store";

const res = (status: number, body: unknown = {}) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
const mockFetch = (r: unknown) => vi.stubGlobal("fetch", vi.fn(async () => r));
afterEach(() => vi.unstubAllGlobals());

const reply = { reply_text: "hi", language: "es", awaiting: "none", options: [], refs: [], data_as_of: null, turn_id: "TRN-1" };
const m = { id: "a", cursor: "2026-09-30T10:00:00+00:00#a", role: "assistant", text: "x", ts: "t" };

describe("api.send", () => {
  it("returns the reply from {data}", async () => {
    mockFetch(res(200, { data: reply }));
    expect(await api.send("hola", "cm-1")).toMatchObject({ kind: "reply", reply: { turn_id: "TRN-1" } });
  });
  it("maps 202 to pending, 401 to expired, other failures and bad bodies to error", async () => {
    mockFetch(res(202, { data: { pending: true } }));
    expect(await api.send("a", "b")).toEqual({ kind: "pending" });
    mockFetch(res(401, { error: { code: "session_expired", message: "" } }));
    expect(await api.send("a", "b")).toEqual({ kind: "expired" });
    mockFetch(res(500));
    expect(await api.send("a", "b")).toEqual({ kind: "error" });
    mockFetch(res(200, { data: { nope: 1 } }));
    expect(await api.send("a", "b")).toEqual({ kind: "error" });
  });
});

describe("api.history and syncHistory", () => {
  it("returns ok, expired, and error for a malformed body", async () => {
    mockFetch(res(200, { data: [m] }));
    expect(await api.history("S-1")).toEqual({ kind: "ok", messages: [m] });
    mockFetch(res(401));
    expect(await api.history("S-1")).toEqual({ kind: "expired" });
    mockFetch(res(200, { data: [{ id: 1 }] }));
    expect(await api.history("S-1")).toEqual({ kind: "error" });
  });
  it("merges on ok and expires the store on 401", async () => {
    const s = createChatStore();
    mockFetch(res(200, { data: [m] }));
    await syncHistory(s, "S-1");
    expect(s.getState().messages).toHaveLength(1);
    mockFetch(res(401));
    await syncHistory(s, "S-1");
    expect(s.getState().expired).toBe(true);
  });
});
