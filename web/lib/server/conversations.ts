import "server-only";
import { appendMessage } from "./messages";
import type { CustomerSession } from "./jwt";
import { endSession } from "./sessions";

const LEFT = { es: "El cliente terminó la conversación.", pt: "O cliente encerrou a conversa." };

/** Ends the token's conversation and, when a person holds it, says so in the transcript they are reading. */
export async function endCurrent(who: CustomerSession): Promise<void> {
  const { control } = await endSession(who.sid, who.sub, who.lang);
  if (control.startsWith("human:")) await appendMessage(who.sid, { role: "system", text: LEFT[who.lang] });
}
