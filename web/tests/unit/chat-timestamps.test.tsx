// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ChatScreen } from "@/components/customer/ChatScreen";
import { fmtTime } from "@/lib/format";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/lib/realtime/useChannel", () => ({ useChannel: () => "live" }));
class RO { observe() {} unobserve() {} disconnect() {} }
globalThis.ResizeObserver ??= RO as unknown as typeof ResizeObserver;
Element.prototype.scrollTo ??= () => {};
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("each customer and assistant message shows its time under the bubble", async () => {
  const q = "2026-10-05T14:05:00.000000+00:00", a = "2026-10-05T14:06:00.000000+00:00";
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ data: [
    { id: "m1", cursor: `${q}#m1`, role: "customer", text: "saldo", ts: q },
    { id: "m2", cursor: `${a}#m2`, role: "assistant", text: "Tu saldo es…", ts: a, meta: { awaiting: "none" } },
  ] })));
  render(<ChatScreen sid="s1" lang="es" embed={false} />);
  await screen.findByText("Tu saldo es…");
  for (const ts of [q, a]) {
    const el = screen.getByText(fmtTime(ts, "es"));
    expect(el.tagName).toBe("TIME");
    expect(el).toHaveAttribute("datetime", ts);
  }
});
