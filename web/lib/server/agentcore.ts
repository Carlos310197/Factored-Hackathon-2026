import "server-only";
import { createHash } from "node:crypto";
import { ChatReply, type Lang } from "@/lib/contract";
import { env } from "./env";

export class AgentError extends Error {
  constructor(readonly kind: "timeout" | "upstream" | "auth", detail = "") { super(`agent ${kind} ${detail}`.trim()); }
}

/** AgentCore needs >= 33 chars; deterministic so every turn of a conversation reuses its runtime session. */
export function runtimeSessionId(sid: string): string {
  return `${sid}-${createHash("sha256").update(sid).digest("hex").slice(0, 32)}`;
}

export async function invokeAgent(a: { token: string; sid: string; message: string; clientMessageId: string; lang: Lang }): Promise<ChatReply> {
  let res: Response;
  try {
    res = await fetch(env().AGENTCORE_INVOKE_URL, {
      method: "POST", cache: "no-store", signal: AbortSignal.timeout(25_000),
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${a.token}`,
        "x-amzn-bedrock-agentcore-runtime-session-id": runtimeSessionId(a.sid),
        "x-amzn-bedrock-agentcore-runtime-custom-message-id": a.clientMessageId,
      },
      body: JSON.stringify({ message: a.message, client_message_id: a.clientMessageId, lang: a.lang }),
    });
  } catch (e) {
    const name = (e as { name?: string }).name;
    throw new AgentError(name === "TimeoutError" || name === "AbortError" ? "timeout" : "upstream", String(e));
  }
  if (!res.ok) {
    await res.body?.cancel().catch(() => {});
    throw new AgentError(res.status === 401 || res.status === 403 ? "auth" : "upstream", `HTTP ${res.status}`);
  }
  try {
    return ChatReply.parse(await res.json());
  } catch (e) {
    throw new AgentError("upstream", `bad reply: ${String(e).slice(0, 200)}`);
  }
}

/** Login-time warm-up: AgentCore starts a microVM per runtime session, so without this a conversation's first turn
 *  pays ~11 s of container start. Fire-and-forget from the OTP route; never throws (failure = a cold first turn). */
export async function warmAgent(a: { token: string; sid: string }): Promise<void> {
  try {
    const res = await fetch(env().AGENTCORE_INVOKE_URL, {
      method: "POST", cache: "no-store", signal: AbortSignal.timeout(30_000),
      headers: { "content-type": "application/json", authorization: `Bearer ${a.token}`,
        "x-amzn-bedrock-agentcore-runtime-session-id": runtimeSessionId(a.sid) },
      body: JSON.stringify({ warmup: true }),
    });
    await res.body?.cancel().catch(() => {});
  } catch { /* cold first turn */ }
}
