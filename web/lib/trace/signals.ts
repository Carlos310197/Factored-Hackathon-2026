/** UI spec §7.3: each signal owns a fixed colour (dataviz reference categorical palette, validated). */
export const SIGNALS = [
  { key: "intent", label: "Intent", kind: "choice", color: "#2a78d6" },
  { key: "target_transaction", label: "Target", kind: "choice", color: "#eb6834" },
  { key: "dispute_reason", label: "Dispute reason", kind: "choice", color: "#1baf7a" },
  { key: "confirmation", label: "Confirmation", kind: "choice", color: "#2a78d6" },
  { key: "asks_for_human", label: "Asks for a human", kind: "flag", color: "#eda100" },
  { key: "reports_unauthorized_use", label: "Reports unauthorized use", kind: "flag", color: "#e87ba4" },
  { key: "legal_or_regulator_threat", label: "Legal or regulator threat", kind: "flag", color: "#008300" },
  { key: "distress", label: "Distress", kind: "flag", color: "#4a3aa7" },
  { key: "injection_attempt", label: "Injection attempt", kind: "flag", color: "#e34948" },
] as const;
export type SignalKey = (typeof SIGNALS)[number]["key"];
export const BELOW_COLOR = "#a7b1be";
export const FLAG_KEYS = SIGNALS.filter((s) => s.kind === "flag").map((s) => s.key);

export const signalOf = (key: string) => SIGNALS.find((s) => s.key === key);
export const signalColor = (key: string) => signalOf(key)?.color ?? BELOW_COLOR;

export const FLAG_VERDICT: Record<string, { icon: "⚑" | "⛔"; text: string }> = {
  reports_unauthorized_use: { icon: "⚑", text: "handoff" },
  legal_or_regulator_threat: { icon: "⚑", text: "handoff" },
  asks_for_human: { icon: "⚑", text: "handoff" },
  distress: { icon: "⚑", text: "offer human" },
  injection_attempt: { icon: "⛔", text: "blocked" },
};
