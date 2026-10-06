import "server-only";
import { GetCommand, QueryCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { doc, isConditionFailure, isoMicro, NotFoundError, tableName, ttl } from "./ddb";

export interface SessionItem { session_id: string; customer_id: string; language: "es" | "pt"; control: string;
  created_at?: string; ended_at?: string; hidden?: boolean }
export interface SessionSummary { session_id: string; created_at: string; language: "es" | "pt"; ended: boolean; preview: string | null }

const PREVIEW_CHARS = 80;
const LIST_MAX = 20;

export async function getSession(sid: string): Promise<SessionItem | null> {
  const r = await doc().send(new GetCommand({ TableName: tableName("sessions"), Key: { session_id: sid }, ConsistentRead: true }));
  return (r.Item as SessionItem | undefined) ?? null;
}

async function preview(sid: string): Promise<string | null> {
  const r = await doc().send(new QueryCommand({
    TableName: tableName("conversation_messages"), KeyConditionExpression: "session_id = :s",
    FilterExpression: "kind = :m AND #r = :c", ExpressionAttributeNames: { "#r": "role" },
    ExpressionAttributeValues: { ":s": sid, ":m": "message", ":c": "customer" },
    Limit: 25, // Limit applies before the filter; the first customer message is always within the first few items
  }));
  const text = (r.Items?.[0]?.text as string | undefined)?.trim();
  return text ? text.slice(0, PREVIEW_CHARS) : null;
}

export async function listCustomerSessions(customerId: string): Promise<SessionSummary[]> {
  const r = await doc().send(new QueryCommand({
    TableName: tableName("sessions"), IndexName: "by_customer", KeyConditionExpression: "customer_id = :c",
    ExpressionAttributeValues: { ":c": customerId }, ScanIndexForward: false, Limit: LIST_MAX * 2,
  }));
  const items = ((r.Items ?? []) as SessionItem[]).filter((i) => !i.hidden).slice(0, LIST_MAX);
  return Promise.all(items.map(async (i) => ({ session_id: i.session_id, created_at: i.created_at!, language: i.language,
    ended: !!i.ended_at, preview: await preview(i.session_id) })));
}

/** A conversation with no turns has no item yet (the agent creates it on the first turn), so this creates it. */
export async function endSession(sid: string, customerId: string, lang: "es" | "pt"): Promise<{ control: string }> {
  const now = isoMicro();
  try {
    const r = await doc().send(new UpdateCommand({
      TableName: tableName("sessions"), Key: { session_id: sid },
      UpdateExpression: "SET ended_at = if_not_exists(ended_at, :now), customer_id = if_not_exists(customer_id, :c), "
        + "#l = if_not_exists(#l, :l), control = if_not_exists(control, :a), created_at = if_not_exists(created_at, :now), "
        + "#t = if_not_exists(#t, :ttl)",
      ConditionExpression: "attribute_not_exists(session_id) OR customer_id = :c",
      ExpressionAttributeNames: { "#l": "language", "#t": "ttl" },
      ExpressionAttributeValues: { ":now": now, ":c": customerId, ":l": lang, ":a": "agent", ":ttl": ttl() },
      ReturnValues: "ALL_NEW",
    }));
    return { control: String(r.Attributes?.control ?? "agent") };
  } catch (e) {
    if (isConditionFailure(e)) throw new NotFoundError(sid);
    throw e;
  }
}

/** The record is kept: bank conversations are retained. */
export async function hideSession(sid: string, customerId: string): Promise<void> {
  try {
    await doc().send(new UpdateCommand({
      TableName: tableName("sessions"), Key: { session_id: sid }, UpdateExpression: "SET #h = :t", // "hidden" is a DynamoDB reserved word
      ConditionExpression: "customer_id = :c", ExpressionAttributeNames: { "#h": "hidden" }, ExpressionAttributeValues: { ":t": true, ":c": customerId },
    }));
  } catch (e) {
    if (isConditionFailure(e)) throw new NotFoundError(sid);
    throw e;
  }
}
