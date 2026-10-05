"use client";
import { Amplify } from "aws-amplify";
import { events } from "aws-amplify/data";
import { QueueEvent, SessionEvent, TraceEvent } from "@/lib/contract";

type Opts = { as: "customer" | "staff"; onResync: () => void; pollMs?: number; onStatus?: (s: "live" | "polling" | "reconnecting") => void };
let configured = false;
const TOKEN_REFRESH_MS = 14 * 60_000;

async function realtimeToken(as: Opts["as"]): Promise<string | null> {
  const res = await fetch(`/api/auth/realtime-token${as === "staff" ? "?as=staff" : ""}`, { cache: "no-store" });
  if (!res.ok) return null;
  try { return ((await res.json()).data.token as string) ?? null; } catch { return null; }
}

function configure(domain: string) {
  if (configured) return;
  Amplify.configure({ API: { Events: { endpoint: `https://${domain}/event`, region: process.env.NEXT_PUBLIC_EVENTS_REGION ?? "us-east-1",
    defaultAuthMode: "lambda" } } });
  configured = true;
}

function schemaFor(channel: string) {
  if (channel.startsWith("/queue")) return QueueEvent;
  if (channel.startsWith("/trace")) return TraceEvent;
  return SessionEvent;
}

/** Load-then-listen (UI spec §3 rule 2): every (re)connect triggers onResync so missed pushes are refetched.
 *  Events are validated against the channel's contract schema; malformed ones are dropped. */
export function connectChannel(channel: string, onEvent: (payload: unknown) => void, opts: Opts): () => void {
  const domain = process.env.NEXT_PUBLIC_EVENTS_HTTP_DOMAIN;
  let stopped = false;
  if (!domain) {
    opts.onStatus?.("polling");
    const id = setInterval(() => { if (!stopped) opts.onResync(); }, opts.pollMs ?? 3000);
    return () => { stopped = true; clearInterval(id); };
  }
  configure(domain);
  const schema = schemaFor(channel);
  let close: (() => void) | null = null;
  let retry = 0;
  let refresh: ReturnType<typeof setTimeout> | undefined;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;

  const deliver = (data: unknown) => {
    try {
      const d = data as { event?: unknown };
      const raw = typeof data === "string" ? JSON.parse(data) : d?.event ?? data;
      const parsed = schema.safeParse(typeof raw === "string" ? JSON.parse(raw) : raw);
      if (parsed.success) onEvent(parsed.data);
      else console.warn("realtime: dropped malformed event", channel);
    } catch {
      console.warn("realtime: dropped unparseable event", channel);
    }
  };

  /** routine = token refresh: the new subscription goes live before the old one closes, no resync or status flip. */
  const open = async (routine = false) => {
    if (stopped) return;
    try {
      const token = await realtimeToken(opts.as);
      if (!token || stopped) throw new Error("no realtime token");
      const ch = await events.connect(channel, { authMode: "lambda", authToken: token });
      const sub = ch.subscribe({ next: deliver, error: () => { if (close === closeThis) reconnect(); } });
      const closeThis = () => { sub.unsubscribe(); ch.close(); };
      if (stopped) { closeThis(); return; }
      const old = close;
      close = closeThis;
      old?.();
      retry = 0;
      if (!routine) { opts.onStatus?.("live"); opts.onResync(); }
      refresh = setTimeout(() => void open(true), TOKEN_REFRESH_MS);
    } catch {
      if (routine) clearTimeout(refresh);
      reconnect();
    }
  };
  const reconnect = () => {
    close?.(); close = null;
    clearTimeout(refresh);
    clearTimeout(retryTimer);
    if (stopped) return;
    opts.onStatus?.("reconnecting");
    opts.onResync();
    retry = Math.min(retry + 1, 5);
    retryTimer = setTimeout(() => void open(), 500 * 2 ** retry);
  };
  void open();
  return () => { stopped = true; close?.(); close = null; clearTimeout(refresh); clearTimeout(retryTimer); };
}
