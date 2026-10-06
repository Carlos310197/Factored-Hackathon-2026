import { CreateTableCommand, DeleteTableCommand, DynamoDBClient } from "@aws-sdk/client-dynamodb";

const S = "S" as const;
export async function createTables(prefix: string, endpoint: string) {
  const c = new DynamoDBClient({ region: "us-east-1", endpoint, credentials: { accessKeyId: "local", secretAccessKey: "local" } });
  const specs = [
    { n: "sessions", k: [["session_id", "HASH"]], gsi: ["by_customer", "customer_id"] },
    { n: "conversation_messages", k: [["session_id", "HASH"], ["sk", "RANGE"]] },
    { n: "decision_records", k: [["session_id", "HASH"], ["sk", "RANGE"]] },
    { n: "handoffs", k: [["handoff_id", "HASH"]], gsi: ["by_status", "status"] },
  ];
  for (const s of specs) {
    await c.send(new DeleteTableCommand({ TableName: `${prefix}-${s.n}` })).catch(() => undefined);
    const attrs = new Map(s.k.map(([a]) => [a, S]));
    if (s.gsi) { attrs.set(s.gsi[1], S); attrs.set("created_at", S); }
    await c.send(new CreateTableCommand({
      TableName: `${prefix}-${s.n}`, BillingMode: "PAY_PER_REQUEST",
      AttributeDefinitions: [...attrs].map(([AttributeName, AttributeType]) => ({ AttributeName, AttributeType })),
      KeySchema: s.k.map(([AttributeName, KeyType]) => ({ AttributeName, KeyType: KeyType as "HASH" | "RANGE" })),
      GlobalSecondaryIndexes: s.gsi ? [{ IndexName: s.gsi[0], Projection: { ProjectionType: "ALL" },
        KeySchema: [{ AttributeName: s.gsi[1], KeyType: "HASH" }, { AttributeName: "created_at", KeyType: "RANGE" }] }] : undefined,
    }));
  }
}
