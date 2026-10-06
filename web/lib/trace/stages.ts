export type Stage = "understand" | "decide" | "act" | "verify";
export const STAGES: { key: Stage; label: string }[] = [
  { key: "understand", label: "Understand" }, { key: "decide", label: "Decide" }, { key: "act", label: "Act" }, { key: "verify", label: "Verify reply" },
];

export function stageOf(node: string, kind: string): Stage | null {
  if (kind === "turn_end") return null;
  if (node === "reply") return "verify";
  if (kind === "route") return "decide";
  if (node === "load_context" || node === "understand") return "understand";
  return "act";
}
