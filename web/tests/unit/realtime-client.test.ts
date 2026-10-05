import { afterEach, describe, expect, it, vi } from "vitest";
import { connectChannel } from "@/lib/realtime/client";

afterEach(() => { vi.useRealTimers(); delete process.env.NEXT_PUBLIC_EVENTS_HTTP_DOMAIN; });

describe("connectChannel without a realtime endpoint", () => {
  it("polls onResync every pollMs and stops on dispose", async () => {
    vi.useFakeTimers();
    const onResync = vi.fn();
    const stop = connectChannel("/session/S-1", () => undefined, { as: "customer", onResync, pollMs: 1000 });
    await vi.advanceTimersByTimeAsync(3100);
    expect(onResync).toHaveBeenCalledTimes(3);
    stop();
    await vi.advanceTimersByTimeAsync(3000);
    expect(onResync).toHaveBeenCalledTimes(3);
  });
});

describe("connectChannel with a realtime endpoint (mocked Amplify, no network)", () => {
  it("resyncs on connect, pushes events, and reconnects after an error", async () => {
    vi.useFakeTimers();
    process.env.NEXT_PUBLIC_EVENTS_HTTP_DOMAIN = "x.example";
    vi.resetModules();
    let handlers: { next: (d: unknown) => void; error: () => void } | undefined;
    const connect = vi.fn(async () => ({ subscribe: (h: typeof handlers) => { handlers = h; return { unsubscribe: () => undefined }; }, close: () => undefined }));
    vi.doMock("aws-amplify", () => ({ Amplify: { configure: () => undefined } }));
    vi.doMock("aws-amplify/data", () => ({ events: { connect } }));
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ data: { token: "T" } }) })));
    const { connectChannel: connectLive } = await import("@/lib/realtime/client");
    const onResync = vi.fn(); const onEvent = vi.fn();
    const stop = connectLive("/session/S-1", onEvent, { as: "customer", onResync });
    await vi.advanceTimersByTimeAsync(10);
    expect(onResync).toHaveBeenCalledTimes(1);
    handlers!.next({ event: { type: "control", control: "agent" } });
    expect(onEvent).toHaveBeenCalledWith({ type: "control", control: "agent" });
    handlers!.error();
    expect(onResync).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(2000);
    expect(connect).toHaveBeenCalledTimes(2);
    stop();
    vi.unstubAllGlobals(); vi.doUnmock("aws-amplify"); vi.doUnmock("aws-amplify/data");
  });
});
