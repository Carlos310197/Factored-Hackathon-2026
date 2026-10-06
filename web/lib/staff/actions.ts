import type { HandoffStatus } from "@/lib/contract";

export type CaseAction = "claim" | "takeover" | "return" | "resolve";

/** Disallowed buttons are hidden, not disabled. */
export function allowedActions(p: { status: HandoffStatus; claimed_by?: string | null }, me: string): CaseAction[] {
  if (p.status === "open") return ["claim"];
  if (p.claimed_by !== me || p.status === "resolved") return [];
  if (p.status === "in_takeover") return ["return", "resolve"];
  return ["takeover", "resolve"];
}

export const REASON_TEXT: Record<string, string> = {
  reports_unauthorized_use: "Unauthorized use", legal_or_regulator_threat: "Legal threat", asks_for_human: "Asked for a person",
  distress: "Distress", injection_attempt: "Injection attempts", amount_over_limit: "Amount over limit", fraud_flag: "Fraud flag",
  fraud_score_high: "High fraud score", confirmation_unclear: "Confirmation unclear", jev_unavailable: "Decisions unavailable",
  customer_request: "Customer request", clarification_limit: "Couldn't clarify",
};
export const reasonText = (code: string) => REASON_TEXT[code] ?? code.replaceAll("_", " ");
export const PRIORITY_WORD = { critical: "Critical", high: "High", medium: "Medium" } as const;
export const ACTION_LABEL: Record<CaseAction, string> = { claim: "Claim", takeover: "Take over chat", return: "Return to assistant", resolve: "Resolve…" };
