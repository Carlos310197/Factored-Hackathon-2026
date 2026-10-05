"use client";
import { useEffect, useRef, useState } from "react";
import { connectChannel } from "./client";

export function useChannel(channel: string | null, onEvent: (payload: unknown) => void,
  opts: { as: "customer" | "staff"; onResync: () => void; pollMs?: number }) {
  const [status, setStatus] = useState<"live" | "polling" | "reconnecting">("polling");
  const ev = useRef(onEvent);
  const resync = useRef(opts.onResync);
  useEffect(() => { ev.current = onEvent; resync.current = opts.onResync; });
  useEffect(() => {
    if (!channel) return;
    return connectChannel(channel, (p) => ev.current(p), { as: opts.as, pollMs: opts.pollMs,
      onResync: () => resync.current(), onStatus: setStatus });
  }, [channel, opts.as, opts.pollMs]);
  return status;
}
