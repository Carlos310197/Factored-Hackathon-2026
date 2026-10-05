import { unmarshall } from "@aws-sdk/util-dynamodb";
import type { DynamoDBBatchResponse, DynamoDBStreamEvent } from "aws-lambda";
import { tableKind, toEvents } from "./map";
import { defaultSigner, publish } from "./publish";

type PublishFn = (channel: string, payloads: object[]) => Promise<void>;

export function makeHandler(publishFn: PublishFn) {
  return async (event: DynamoDBStreamEvent): Promise<DynamoDBBatchResponse> => {
    const batchItemFailures: { itemIdentifier: string }[] = [];
    for (const record of event.Records) { // in order: a session's messages keep their order
      try {
        const kind = tableKind(record.eventSourceARN ?? "");
        const image = record.dynamodb?.NewImage;
        if (!kind || !image) continue;
        const events = toEvents(kind, unmarshall(image as never), record.eventName ?? "");
        const byChannel = new Map<string, object[]>();
        for (const e of events) byChannel.set(e.channel, [...(byChannel.get(e.channel) ?? []), e.payload]);
        for (const [channel, payloads] of byChannel) await publishFn(channel, payloads);
      } catch (err) {
        console.error("publish failed", record.dynamodb?.SequenceNumber, err);
        batchItemFailures.push({ itemIdentifier: record.dynamodb?.SequenceNumber ?? "" });
      }
    }
    return { batchItemFailures };
  };
}

const signer = defaultSigner(process.env.AWS_REGION ?? "us-east-1");
export const handler = makeHandler((channel, payloads) =>
  publish(channel, payloads, { httpDomain: process.env.EVENTS_HTTP_DOMAIN as string, signer }));
