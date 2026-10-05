"use client";
import { Amplify } from "aws-amplify";
import { events } from "aws-amplify/data";

type Opts = { as: "customer" | "staff"; onResync: () => void; pollMs?: number; onStatus?: (s: "live" | "polling" | "reconnecting") => void };
let configured = false;
const TOKEN_REFRESH_MS = 14 * 60_000;

async function realtimeToken(as: Opts["as"]): Promise<string | null> {
  const res = await fetch(`/api/auth/realtime-token${as === "staff" ? "?as=staff" : ""}`, { cache: "no-store" });
  if (!res.ok) return null;
  return (await res.json()).data.token as string;
}

function configure(domain: string) {
  if (configured) return;
  Amplify.configure({ API: { Events: { endpoint: `https://${domain}/event`, region: process.env.NEXT_PUBLIC_EVENTS_REGION ?? "us-east-2",
    defaultAuthMode: "lambda" } } });
  configured = true;
}

/** Load-then-listen (UI spec §3 rule 2): every (re)connect triggers onResync so missed pushes are refetched. */
export function connectChannel(channel: string, onEvent: (payload: unknown) => void, opts: Opts): () => void {
  const domain = process.env.NEXT_PUBLIC_EVENTS_HTTP_DOMAIN;
  let stopped = false;
  if (!domain) {
    opts.onStatus?.("polling");
    const id = setInterval(() => { if (!stopped) opts.onResync(); }, opts.pollMs ?? 3000);
    return () => { stopped = true; clearInterval(id); };
  }
  configure(domain);
  let close: (() => void) | null = null;
  let retry = 0;
  let refresh: ReturnType<typeof setTimeout> | undefined;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;

  const open = async () => {
    if (stopped) return;
    try {
      const token = await realtimeToken(opts.as);
      if (!token) throw new Error("no realtime token");
      const ch = await events.connect(channel, { authMode: "lambda", authToken: token });
      const sub = ch.subscribe({
        next: (data: unknown) => {
          const d = data as { event?: unknown };
          onEvent(typeof d === "string" ? JSON.parse(d) : d?.event ?? d);
        },
        error: () => reconnect(),
      });
      close = () => { sub.unsubscribe(); ch.close(); };
      retry = 0;
      opts.onStatus?.("live");
      opts.onResync();
      refresh = setTimeout(() => reconnect(), TOKEN_REFRESH_MS);
    } catch {
      reconnect();
    }
  };
  const reconnect = () => {
    close?.(); close = null;
    if (refresh) clearTimeout(refresh);
    if (stopped) return;
    opts.onStatus?.("reconnecting");
    opts.onResync();
    retry = Math.min(retry + 1, 5);
    retryTimer = setTimeout(open, 500 * 2 ** retry);
  };
  void open();
  return () => { stopped = true; close?.(); clearTimeout(refresh); clearTimeout(retryTimer); };
}
