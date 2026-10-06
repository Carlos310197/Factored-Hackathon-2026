/** Client message ids double as idempotency keys; the agent accepts ^[A-Za-z0-9_-]{8,64}$.
 * getRandomValues, not randomUUID: randomUUID exists only in secure contexts, and the demo is served over plain HTTP. */
export function newClientMessageId(): string {
  const b = crypto.getRandomValues(new Uint8Array(16));
  return `cm-${Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("")}`;
}
