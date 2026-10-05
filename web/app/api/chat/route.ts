import { after, type NextRequest } from "next/server";
import { z } from "zod";
import { AgentError, invokeAgent } from "@/lib/server/agentcore";
import { env } from "@/lib/server/env";
import { fail, ok, readJson } from "@/lib/server/http";
import { appendMessage, claimMessageId } from "@/lib/server/messages";
import { customerFrom } from "@/lib/server/session";
import { getSession } from "@/lib/server/sessions";

const Body = z.object({
  message: z.string().trim().min(1).max(2000),
  client_message_id: z.string().regex(/^[A-Za-z0-9_-]{8,64}$/),
});

export async function POST(req: NextRequest) {
  const who = await customerFrom(req);
  if (!who) return fail("session_expired", "Sign in again", 401);
  const body = await readJson(req, Body);
  if (body instanceof Response) return body;

  const session = await getSession(who.sid);
  if (session && session.control !== "agent") {  // a human holds the conversation: never call the runtime (spec §3 rule 5)
    if (await claimMessageId(who.sid, body.client_message_id)) {
      await appendMessage(who.sid, { role: "customer", text: body.message, id: body.client_message_id });
    }
    return ok({ reply_text: "", language: who.lang, awaiting: "human", options: [], refs: [], data_as_of: null, turn_id: null });
  }

  const call = () => invokeAgent({ token: who.token, sid: who.sid, message: body.message, clientMessageId: body.client_message_id, lang: who.lang });
  if (env().CHAT_ASYNC === "1") {  // Task 1 Step 4 fallback: reply arrives on /session/<sid>
    after(async () => {
      try { await call(); } catch (e) {
        console.error("async turn failed", e);
        const text = who.lang === "pt" ? "O assistente não respondeu. Tente novamente." : "El asistente no respondió. Inténtalo de nuevo.";
        await appendMessage(who.sid, { role: "system", text, meta: { control: "agent_error" } }).catch(() => {});
      }
    });
    return ok({ pending: true }, 202);
  }
  try {
    const reply = await call();
    if (reply.error === "session_expired" || reply.error === "auth_required") return fail("session_expired", "Sign in again", 401);
    return ok(reply);
  } catch (e) {
    if (e instanceof AgentError && e.kind === "auth") return fail("session_expired", "Sign in again", 401);
    if (e instanceof AgentError) return fail(`agent_${e.kind}`, "The assistant did not answer", e.kind === "timeout" ? 504 : 502);
    throw e;
  }
}
