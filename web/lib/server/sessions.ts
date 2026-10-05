import "server-only";
import { GetCommand } from "@aws-sdk/lib-dynamodb";
import { doc, tableName } from "./ddb";

export interface SessionItem { session_id: string; customer_id: string; language: "es" | "pt"; control: string }

export async function getSession(sid: string): Promise<SessionItem | null> {
  const r = await doc().send(new GetCommand({ TableName: tableName("sessions"), Key: { session_id: sid }, ConsistentRead: true }));
  return (r.Item as SessionItem | undefined) ?? null;
}
