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

describe("connectChannel hardening (mocked Amplify)", () => {
  const setup = async (connectImpl: (...a: unknown[]) => Promise<unknown>) => {
    vi.useFakeTimers();
    process.env.NEXT_PUBLIC_EVENTS_HTTP_DOMAIN = "x.example";
    vi.resetModules();
    const connect = vi.fn(connectImpl);
    vi.doMock("aws-amplify", () => ({ Amplify: { configure: () => undefined } }));
    vi.doMock("aws-amplify/data", () => ({ events: { connect } }));
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ data: { token: "T" } }) })));
    const { connectChannel: c } = await import("@/lib/realtime/client");
    return { c, connect };
  };
  const cleanup = () => { vi.unstubAllGlobals(); vi.doUnmock("aws-amplify"); vi.doUnmock("aws-amplify/data"); };
  const channelFake = (log: string[], name: string, hs: { h?: { next: (d: unknown) => void } }) => ({
    subscribe: (h: { next: (d: unknown) => void }) => { hs.h = h; return { unsubscribe: () => log.push(`unsub ${name}`) }; },
    close: () => log.push(`close ${name}`),
  });

  it("closes a channel whose connect resolves after dispose", async () => {
    const log: string[] = [];
    let release!: () => void;
    const { c } = await setup(async () => { await new Promise<void>((r) => { release = r; }); return channelFake(log, "A", {}); });
    const onResync = vi.fn();
    const stop = c("/session/S-1", () => undefined, { as: "customer", onResync });
    await vi.advanceTimersByTimeAsync(10);
    stop();
    release();
    await vi.advanceTimersByTimeAsync(10);
    expect(log).toEqual(["unsub A", "close A"]);
    expect(onResync).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(15 * 60_000);
    cleanup();
  });

  it("drops malformed and unparseable events, delivers valid ones", async () => {
    const hs: { h?: { next: (d: unknown) => void } } = {};
    const { c } = await setup(async () => channelFake([], "A", hs));
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const onEvent = vi.fn();
    const stop = c("/session/S-1", onEvent, { as: "customer", onResync: vi.fn() });
    await vi.advanceTimersByTimeAsync(10);
    hs.h!.next("not json{");
    hs.h!.next({ event: { type: "message", id: 1 } });
    hs.h!.next({ event: { type: "control", control: "agent" } });
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({ type: "control", control: "agent" });
    stop();
    cleanup();
  });

  it("refreshes the token by subscribing anew before closing the old channel, with no resync", async () => {
    const log: string[] = [];
    let n = 0;
    const { c, connect } = await setup(async () => channelFake(log, `ch${++n}`, {}));
    const onResync = vi.fn(); const onStatus = vi.fn();
    const stop = c("/session/S-1", () => undefined, { as: "customer", onResync, onStatus });
    await vi.advanceTimersByTimeAsync(10);
    await vi.advanceTimersByTimeAsync(14 * 60_000 + 10);
    expect(connect).toHaveBeenCalledTimes(2);
    expect(log).toEqual(["unsub ch1", "close ch1"]);
    expect(onResync).toHaveBeenCalledTimes(1);
    expect(onStatus.mock.calls.map((x) => x[0])).toEqual(["live"]);
    stop();
    cleanup();
  });
});
