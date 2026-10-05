import { afterEach, describe, expect, it, vi } from "vitest";
import { IdpError, idp } from "@/lib/server/idp";

afterEach(() => vi.unstubAllGlobals());
const reply = (body: string, status = 200) => vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { status })));

describe("idp client", () => {
  it("turns a malformed or non-JSON reply into IdpError(502)", async () => {
    reply('{"nope":1}');
    await expect(idp.login("u", "p")).rejects.toMatchObject({ status: 502 });
    reply("<html>");
    await expect(idp.login("u", "p")).rejects.toBeInstanceOf(IdpError);
  });
  it("maps IdP statuses to ours: 4xx pass through, 5xx become 503", () => {
    expect([400, 422, 401, 403, 500, 502, 503].map((s) => new IdpError(s).httpStatus)).toEqual([400, 400, 401, 401, 503, 503, 503]);
  });
});
