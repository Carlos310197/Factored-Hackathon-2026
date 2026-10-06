import "server-only";
import { QueryCommand } from "@aws-sdk/lib-dynamodb";
import { CustomerCase } from "@/lib/contract";
import { doc, tableName } from "./ddb";

export async function listCustomerCases(customerId: string): Promise<CustomerCase[]> {
  const r = await doc().send(new QueryCommand({ TableName: tableName("disputes"), IndexName: "by_customer",
    KeyConditionExpression: "customer_id = :c", ExpressionAttributeValues: { ":c": customerId }, ScanIndexForward: false, Limit: 20 }));
  return (r.Items ?? []).flatMap((i) => { const c = CustomerCase.safeParse(i); return c.success ? [c.data] : []; });
}
