import { z } from "zod";

export const Lang = z.enum(["es", "pt"]);
export type Lang = z.infer<typeof Lang>;
export const Awaiting = z.enum(["none", "clarification", "confirmation", "human"]);
export type Awaiting = z.infer<typeof Awaiting>;

export const Summary = z.object({
  merchant: z.string(), date: z.string(), amount: z.number().nullish(),
  currency: z.string().nullish(), reason_code: z.string().nullish(), // the agent store drops None keys
  card_hash: z.string().nullish(),  // the confirm button sends confirm:<card_hash>; the agent checks equality
});
export type Summary = z.infer<typeof Summary>;

/** POST /invocations response (UI spec §4.7) */
export const ChatReply = z.object({
  reply_text: z.string(),
  language: Lang.catch("es"),
  awaiting: Awaiting,
  options: z.array(z.string()).default([]),
  refs: z.array(z.string()).default([]),
  data_as_of: z.string().nullable().default(null),
  turn_id: z.string().nullable().default(null),
  summary: Summary.optional(),
  error: z.string().optional(),
});
export type ChatReply = z.infer<typeof ChatReply>;

export const MessageMeta = z.object({
  awaiting: Awaiting.optional(), options: z.array(z.string()).optional(), refs: z.array(z.string()).optional(),
  summary: Summary.optional(), data_as_of: z.string().optional(), control: z.string().optional(),
  agent_name: z.string().optional(), error_code: z.string().optional(),
});
export type MessageMeta = z.infer<typeof MessageMeta>;

export const Role = z.enum(["customer", "assistant", "agent", "system"]);
export const ChatMessage = z.object({
  id: z.string(), cursor: z.string(), role: Role, text: z.string(),
  turn_id: z.string().nullish(), author: z.string().nullish(), meta: MessageMeta.nullish(), ts: z.string(),
});
export type ChatMessage = z.infer<typeof ChatMessage>;

export const SessionEvent = z.discriminatedUnion("type", [
  ChatMessage.extend({ type: z.literal("message") }),
  z.object({ type: z.literal("control"), control: z.string(), agent_name: z.string().nullish() }),
  z.object({ type: z.literal("progress"), turn_id: z.string(), stage: z.enum(["understand", "decide", "act", "verify"]) }),
]);
export type SessionEvent = z.infer<typeof SessionEvent>;

export const HandoffStatus = z.enum(["open", "claimed", "in_takeover", "returned", "resolved"]);
export type HandoffStatus = z.infer<typeof HandoffStatus>;
export const Priority = z.enum(["critical", "high", "medium"]);
export type Priority = z.infer<typeof Priority>;

export const HandoffRow = z.object({
  handoff_id: z.string(), session_id: z.string(), status: HandoffStatus, priority: Priority,
  reason_codes: z.array(z.string()), language: Lang, created_at: z.string(), claimed_by: z.string().nullish(),
});
export type HandoffRow = z.infer<typeof HandoffRow>;
export const QueueEvent = HandoffRow.extend({ type: z.literal("handoff") });

export const TraceEvent = z.discriminatedUnion("type", [
  z.object({ type: z.literal("record"), turn_id: z.string(), seq: z.number(), node: z.string(), kind: z.string() }),
  z.object({ type: z.literal("turn_complete"), turn_id: z.string() }),
]);
export type TraceEvent = z.infer<typeof TraceEvent>;

export const RESOLUTION_CODES = ["resolved_by_agent", "dispute_filed_manually", "no_action_needed", "referred_to_phone"] as const;
export const ResolutionCode = z.enum(RESOLUTION_CODES);
export type ResolutionCode = z.infer<typeof ResolutionCode>;

export const HandoffPacket = z.object({
  schema_version: z.literal("handoff.v1"),
  handoff_id: z.string(), created_at: z.string(), status: HandoffStatus,
  claimed_by: z.string().nullish(), claimed_at: z.string().nullish(),
  resolution: z.object({ code: ResolutionCode, note: z.string(), by: z.string(), at: z.string() }).nullish(),
  session_id: z.string(), customer_id: z.string(), language: Lang, data_as_of: z.string(), priority: Priority,
  reason_codes: z.array(z.string()),
  customer_request: z.object({ original: z.string(), en: z.string() }),
  verified_facts: z.array(z.object({ fact: z.string(), receipt_id: z.string() })),
  actions_taken: z.array(z.object({ action: z.string(), result: z.string(), receipt_id: z.string().nullish() })),
  decisions: z.array(z.object({ question: z.string(), value: z.union([z.string(), z.number()]), p: z.number().nullish(), question_set: z.string(), thresholds: z.string() })),
  policy_checks: z.array(z.object({ rule: z.string(), passed: z.boolean(), detail: z.string().nullish() })),
  open_questions: z.array(z.string()).max(3),
  transcript_ref: z.string(),
});
export type HandoffPacket = z.infer<typeof HandoffPacket>;

export interface ApiError { error: { code: string; message: string } }
