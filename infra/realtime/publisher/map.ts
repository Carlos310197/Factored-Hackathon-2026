export type TableKind = "handoffs" | "decision_records" | "conversation_messages";
export type ChannelEvent = Record<string, unknown> & { type: string };
export interface OutEvent { channel: string; payload: ChannelEvent }
type Image = Record<string, unknown>;

const KINDS: TableKind[] = ["handoffs", "decision_records", "conversation_messages"];

export function tableKind(eventSourceArn: string): TableKind | null {
  const m = /:table\/([^/]+)\/stream\//.exec(eventSourceArn);
  if (!m) return null;
  return KINDS.find((k) => m[1].endsWith(`-${k}`)) ?? null;
}

const s = (v: unknown) => (typeof v === "string" ? v : undefined);

// Mirrors stageOf in web/lib/trace/stages.ts (separate package; keep in sync).
function stageOf(node: string, kind: string): string | null {
  if (kind === "turn_end") return null;
  if (node === "reply") return "verify";
  if (kind === "route") return "decide";
  if (node === "load_context" || node === "understand") return "understand";
  return "act";
}

export function toEvents(kind: TableKind, img: Image, eventName: string): OutEvent[] {
  if (eventName === "REMOVE") return [];
  if (kind === "conversation_messages") {
    if (eventName !== "INSERT" || img.kind !== "message") return [];
    const channel = `/session/${img.session_id}`;
    const meta = (img.meta as Image | undefined) ?? undefined;
    const out: OutEvent[] = [{ channel, payload: { type: "message", id: s(img.message_id), cursor: s(img.sk), role: s(img.role),
      text: s(img.text) ?? "", turn_id: s(img.turn_id), author: s(img.author), meta, ts: s(img.ts) } }];
    if (img.role === "system" && meta && typeof meta.control === "string") {
      out.push({ channel, payload: { type: "control", control: meta.control, agent_name: s(meta.agent_name) } });
    }
    return out;
  }
  if (kind === "handoffs") {
    return [{ channel: "/queue/all", payload: { type: "handoff", handoff_id: s(img.handoff_id), session_id: s(img.session_id),
      status: s(img.status), priority: s(img.priority), reason_codes: (img.reason_codes as string[]) ?? [],
      language: s(img.language), created_at: s(img.created_at), claimed_by: s(img.claimed_by) } }];
  }
  if (eventName !== "INSERT") return [];
  const channel = `/trace/${img.session_id}`;
  const out: OutEvent[] = [{ channel, payload: { type: "record", turn_id: s(img.turn_id), seq: img.seq as number,
    node: s(img.node), kind: s(img.kind) } }];
  if (img.kind === "turn_end") out.push({ channel, payload: { type: "turn_complete", turn_id: s(img.turn_id) } });
  const stage = stageOf(String(img.node), String(img.kind));  // customer-facing progress: stage only, never record data
  if (stage) out.push({ channel: `/session/${img.session_id}`, payload: { type: "progress", turn_id: s(img.turn_id), stage } });
  return out;
}
