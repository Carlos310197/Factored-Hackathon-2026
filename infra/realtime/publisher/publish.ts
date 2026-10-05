import { Sha256 } from "@aws-crypto/sha256-js";
import { defaultProvider } from "@aws-sdk/credential-provider-node";
import { HttpRequest } from "@smithy/protocol-http";
import { SignatureV4 } from "@smithy/signature-v4";

export interface Signer { sign(req: HttpRequest): Promise<{ headers: Record<string, string> }> }
export interface PublishDeps { httpDomain: string; signer: Signer; fetchImpl?: typeof fetch }

const MAX_EVENTS_PER_REQUEST = 5;

export function defaultSigner(region: string): Signer {
  return new SignatureV4({ service: "appsync", region, credentials: defaultProvider(), sha256: Sha256 }) as unknown as Signer;
}

export async function publish(channel: string, payloads: object[], deps: PublishDeps): Promise<void> {
  const doFetch = deps.fetchImpl ?? fetch;
  for (let i = 0; i < payloads.length; i += MAX_EVENTS_PER_REQUEST) {
    const body = JSON.stringify({ channel, events: payloads.slice(i, i + MAX_EVENTS_PER_REQUEST).map((p) => JSON.stringify(p)) });
    const req = new HttpRequest({ method: "POST", protocol: "https:", hostname: deps.httpDomain, path: "/event",
      headers: { "content-type": "application/json", host: deps.httpDomain }, body });
    const signed = await deps.signer.sign(req);
    const res = await doFetch(`https://${deps.httpDomain}/event`, { method: "POST", headers: signed.headers, body });
    if (!res.ok) throw new Error(`publish ${channel} failed: HTTP ${res.status}`);
    const parsed = (await res.json().catch(() => ({}))) as { failed?: unknown[] };
    if (parsed.failed && parsed.failed.length > 0) throw new Error(`publish ${channel}: ${parsed.failed.length} events failed`);
  }
}
