/** Client message ids double as idempotency keys (UI spec §4.3); the agent accepts ^[A-Za-z0-9_-]{8,64}$. */
export function newClientMessageId(): string {
  return `cm-${crypto.randomUUID().replaceAll("-", "")}`;
}
