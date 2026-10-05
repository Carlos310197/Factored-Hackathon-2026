import { describe, expect, it, vi } from "vitest";
import { newClientMessageId } from "@/lib/ids";

describe("newClientMessageId", () => {
  it("matches the agent's accepted message-id pattern and is unique", () => {
    const ids = new Set(Array.from({ length: 200 }, () => newClientMessageId()));
    expect(ids.size).toBe(200);
    for (const id of ids) expect(id).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
  });

  it("works without crypto.randomUUID (insecure context: plain-HTTP demo deploy)", () => {
    vi.stubGlobal("crypto", { getRandomValues: globalThis.crypto.getRandomValues.bind(globalThis.crypto) });
    try {
      expect(newClientMessageId()).toMatch(/^cm-[0-9a-f]{32}$/);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
