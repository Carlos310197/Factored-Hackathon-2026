import "server-only";
import { QueryCommand } from "@aws-sdk/lib-dynamodb";
import { doc, tableName } from "./ddb";

export interface DecisionRecord {
  session_id: string; sk: string; turn_id: string; seq: number; node: string; kind: string; ts: string;
  payload: Record<string, unknown>; versions: Record<string, string>; latency_ms?: number;
}

export async function listRecords(sid: string, turnId?: string): Promise<DecisionRecord[]> {
  const items: DecisionRecord[] = [];
  let start: Record<string, unknown> | undefined;
  do {
    const r = await doc().send(new QueryCommand({
      TableName: tableName("decision_records"),
      KeyConditionExpression: turnId ? "session_id = :s AND begins_with(sk, :t)" : "session_id = :s",
      ExpressionAttributeValues: turnId ? { ":s": sid, ":t": `${turnId}#` } : { ":s": sid },
      ExclusiveStartKey: start,
    }));
    items.push(...((r.Items ?? []) as DecisionRecord[]));
    start = r.LastEvaluatedKey;
  } while (start);
  return items;
}
