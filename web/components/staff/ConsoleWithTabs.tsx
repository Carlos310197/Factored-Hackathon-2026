"use client";
import { useEffect, useState } from "react";
import type { TraceTurn } from "@/lib/trace/viewModel";
import { Console, type CaseData, type Tab } from "./Console";
import { ConversationTab } from "./ConversationTab";
import { PacketTab, whyBars } from "./PacketTab";

type Me = { sub: string; name: string };

function useTrace(sid: string) {
  const [turns, setTurns] = useState<TraceTurn[]>([]);
  useEffect(() => {
    let live = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTurns([]); // never show the previous case's trace
    fetch(`/api/trace/${encodeURIComponent(sid)}`, { cache: "no-store" })
      .then(async (r) => { if (r.ok && live) setTurns((await r.json()).data); })
      .catch(() => {}); // no trace: the packet shows its fallback line
    return () => { live = false; };
  }, [sid]);
  return turns;
}

function Tabs({ tab, c, me }: { tab: Tab; c: CaseData; me: Me }) {
  const turns = useTrace(c.packet.session_id);
  if (tab === "packet") return <PacketTab packet={c.packet} why={whyBars(turns)} />;
  if (tab === "conversation") return <ConversationTab sid={c.packet.session_id} lang={c.packet.language} control={c.control} me={me} />;
  return <p className="text-sm text-c-muted">Trace tab arrives in the next unit.</p>; // unit 73
}

export function ConsoleWithTabs(props: { me: Me; initialId?: string }) {
  return <Console {...props} renderTab={(tab, c) => <Tabs tab={tab} c={c} me={props.me} />} />;
}
