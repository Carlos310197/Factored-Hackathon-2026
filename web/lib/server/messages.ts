import "server-only";
import { PutCommand, QueryCommand } from "@aws-sdk/lib-dynamodb";
import { ChatMessage, type MessageMeta } from "@/lib/contract";
import { newClientMessageId } from "@/lib/ids";
import { doc, isConditionFailure, isoMicro, tableName, ttl } from "./ddb";


type Item = Record<string, unknown>;
const toMessage = (i: Item): ChatMessage => ChatMessage.parse({
  id: i.message_id, cursor: i.sk, role: i.role, text: i.text ?? "", turn_id: i.turn_id, author: i.author, meta: i.meta, ts: i.ts });

export async function listMessages(sid: string, after?: string): Promise<ChatMessage[]> {
  const out: ChatMessage[] = [];
  let start: Item | undefined;
  do {
    const r = await doc().send(new QueryCommand({
      TableName: tableName("conversation_messages"),
      KeyConditionExpression: after ? "session_id = :s AND sk > :a" : "session_id = :s",
      FilterExpression: "kind = :m",
      ExpressionAttributeValues: { ":s": sid, ":m": "message", ...(after ? { ":a": after } : {}) },
      ExclusiveStartKey: start, ConsistentRead: true,
    }));
    out.push(...(r.Items ?? []).map(toMessage));
    start = r.LastEvaluatedKey;
  } while (start);
  return out;
}

export async function appendMessage(sid: string, m: { role: ChatMessage["role"]; text: string; author?: string;
  meta?: MessageMeta; id?: string }): Promise<ChatMessage> {
  const ts = isoMicro();
  const id = m.id ?? newClientMessageId();
  const item = { session_id: sid, sk: `${ts}#${id}`, kind: "message", message_id: id, role: m.role, text: m.text,
    author: m.author, meta: m.meta, ts, ttl: ttl() };
  await doc().send(new PutCommand({ TableName: tableName("conversation_messages"), Item: item }));
  return toMessage(item);
}

/** Same idempotency marker as the agent (`~idem#<id>`). */
export async function claimMessageId(sid: string, id: string): Promise<boolean> {
  try {
    await doc().send(new PutCommand({ TableName: tableName("conversation_messages"),
      Item: { session_id: sid, sk: `~idem#${id}`, kind: "idem", message_id: id, state: "done", ttl: ttl() },
      ConditionExpression: "attribute_not_exists(sk)" }));
    return true;
  } catch (e) {
    if (isConditionFailure(e)) return false;
    throw e;
  }
}
