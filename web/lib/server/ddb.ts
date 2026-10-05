import "server-only";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import { env } from "./env";

export class ConflictError extends Error {}
export class NotFoundError extends Error {}

export const ttl = () => Math.floor(Date.now() / 1000) + 90 * 86400;

let client: DynamoDBDocumentClient | undefined;
export function doc(): DynamoDBDocumentClient {
  const e = env();
  client ??= DynamoDBDocumentClient.from(new DynamoDBClient({ region: e.AWS_REGION, endpoint: e.DYNAMODB_ENDPOINT }),
    { marshallOptions: { removeUndefinedValues: true } });
  return client;
}
export const tableName = (name: string) => `${env().TABLE_PREFIX}-${name}`;

/** Same shape as the agent's _iso (microseconds, +00:00) so JS- and Python-written sort keys interleave correctly. */
export function isoMicro(d: Date = new Date()): string {
  return `${d.toISOString().slice(0, 23)}000+00:00`;
}

export function isConditionFailure(e: unknown): boolean {
  const x = e as { name?: string; CancellationReasons?: { Code?: string }[] };
  if (x?.name === "ConditionalCheckFailedException") return true;
  return x?.name === "TransactionCanceledException" && !!x.CancellationReasons?.some((r) => r.Code === "ConditionalCheckFailed");
}
