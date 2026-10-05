export type DemoMessage =
  | { type: "demo:auth"; step: "otp_verified" | "token_issued" }
  | { type: "demo:session"; sid: string }
  | { type: "demo:turn-start" }
  | { type: "demo:turn-reply"; turn_id: string | null }
  | { type: "demo:prefill"; text: string };

/** Embedded /chat talks to /demo (same origin only). */
export function notifyParent(msg: DemoMessage) {
  if (typeof window !== "undefined" && window.parent !== window) window.parent.postMessage(msg, window.location.origin);
}

export function isDemoMessage(e: MessageEvent): e is MessageEvent<DemoMessage> {
  return e.origin === window.location.origin && typeof e.data?.type === "string" && e.data.type.startsWith("demo:");
}
