import "server-only";
import { GetCommand, QueryCommand, TransactWriteCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { HandoffPacket, HandoffRow, type HandoffStatus, type ResolutionCode } from "@/lib/contract";
import { t } from "@/lib/i18n";
import { newClientMessageId } from "@/lib/ids";
import { doc, isConditionFailure, isoMicro, NotFoundError, ConflictError, tableName, ttl } from "./ddb";

const PRIORITY_RANK = { critical: 0, high: 1, medium: 2 } as const;
const H = () => tableName("handoffs");

export async function listHandoffs(statuses: HandoffStatus[]): Promise<HandoffRow[]> {
  const rows: HandoffRow[] = [];
  for (const status of statuses) {
    const r = await doc().send(new QueryCommand({ TableName: H(), IndexName: "by_status",
      KeyConditionExpression: "#s = :s", ExpressionAttributeNames: { "#s": "status" }, ExpressionAttributeValues: { ":s": status } }));
    rows.push(...(r.Items ?? []).map((i) => HandoffRow.parse(i)));
  }
  return rows.sort((a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] || a.created_at.localeCompare(b.created_at));
}

export async function getHandoff(id: string): Promise<HandoffPacket | null> {
  const r = await doc().send(new GetCommand({ TableName: H(), Key: { handoff_id: id }, ConsistentRead: true }));
  return r.Item ? HandoffPacket.parse(r.Item) : null;
}

async function mustGet(id: string): Promise<HandoffPacket> {
  const p = await getHandoff(id);
  if (!p) throw new NotFoundError("not_found");
  return p;
}

async function guarded<T>(fn: () => Promise<T>): Promise<T> {
  try { return await fn(); } catch (e) { if (isConditionFailure(e)) throw new ConflictError("precondition_failed"); throw e; }
}

function systemMessage(sid: string, text: string, meta: Record<string, string>) {
  const ts = isoMicro();
  const id = newClientMessageId();
  return { Put: { TableName: tableName("conversation_messages"), Item: { session_id: sid, sk: `${ts}#${id}`, kind: "message",
    message_id: id, role: "system", text, meta, ts, ttl: ttl() } } };
}

export async function claim(id: string, agent: string): Promise<HandoffPacket> {
  await guarded(() => doc().send(new UpdateCommand({ TableName: H(), Key: { handoff_id: id },
    ConditionExpression: "#s = :open", UpdateExpression: "SET #s = :claimed, claimed_by = :a, claimed_at = :now",
    ExpressionAttributeNames: { "#s": "status" },
    ExpressionAttributeValues: { ":open": "open", ":claimed": "claimed", ":a": agent, ":now": new Date().toISOString() } })));
  return mustGet(id);
}

export async function takeover(id: string, agent: string, agentName: string): Promise<HandoffPacket> {
  const p = await mustGet(id);
  const control = `human:${agent}`;
  await guarded(() => doc().send(new TransactWriteCommand({ TransactItems: [
    { Update: { TableName: H(), Key: { handoff_id: id }, ConditionExpression: "#s IN (:claimed, :returned) AND claimed_by = :a",
      UpdateExpression: "SET #s = :tk", ExpressionAttributeNames: { "#s": "status" },
      ExpressionAttributeValues: { ":claimed": "claimed", ":returned": "returned", ":a": agent, ":tk": "in_takeover" } } },
    { Update: { TableName: tableName("sessions"), Key: { session_id: p.session_id }, UpdateExpression: "SET control = :c",
      ConditionExpression: "attribute_exists(session_id) AND control = :agent", ExpressionAttributeValues: { ":c": control, ":agent": "agent" } } },
    systemMessage(p.session_id, t(p.language).agentJoined(agentName), { control, agent_name: agentName }),
  ] })));
  return mustGet(id);
}

export async function returnToAssistant(id: string, agent: string): Promise<HandoffPacket> {
  const p = await mustGet(id);
  await guarded(() => doc().send(new TransactWriteCommand({ TransactItems: [
    { Update: { TableName: H(), Key: { handoff_id: id }, ConditionExpression: "#s = :tk AND claimed_by = :a",
      UpdateExpression: "SET #s = :ret", ExpressionAttributeNames: { "#s": "status" },
      ExpressionAttributeValues: { ":tk": "in_takeover", ":a": agent, ":ret": "returned" } } },
    { Update: { TableName: tableName("sessions"), Key: { session_id: p.session_id }, UpdateExpression: "SET control = :c", ConditionExpression: "control = :mine",
      ExpressionAttributeValues: { ":c": "agent", ":mine": `human:${agent}` } } },
    systemMessage(p.session_id, t(p.language).backToAssistant, { control: "agent" }),
  ] })));
  return mustGet(id);
}

export async function resolve(id: string, agent: string, code: ResolutionCode, note: string): Promise<HandoffPacket> {
  const p = await mustGet(id);
  const resolution = { code, note, by: agent, at: new Date().toISOString() };
  const items: NonNullable<ConstructorParameters<typeof TransactWriteCommand>[0]["TransactItems"]> = [
    { Update: { TableName: H(), Key: { handoff_id: id },
      ConditionExpression: "#s = :prev AND #s <> :resolved AND claimed_by = :a", // the read status decides the session reset, so a stale read conflicts
      UpdateExpression: "SET #s = :res, resolution = :r", ExpressionAttributeNames: { "#s": "status" },
      ExpressionAttributeValues: { ":prev": p.status, ":a": agent, ":res": "resolved", ":resolved": "resolved", ":r": resolution } } },
  ];
  if (p.status === "in_takeover") {
    items.push({ Update: { TableName: tableName("sessions"), Key: { session_id: p.session_id }, UpdateExpression: "SET control = :c",
      ConditionExpression: "attribute_exists(session_id)", ExpressionAttributeValues: { ":c": "agent" } } });
    items.push(systemMessage(p.session_id, t(p.language).backToAssistant, { control: "agent" }));
  }
  await guarded(() => doc().send(new TransactWriteCommand({ TransactItems: items })));
  return mustGet(id);
}
