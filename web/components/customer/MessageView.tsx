"use client";
import { MessagePrimitive, useAuiState, type ThreadMessageLike } from "@assistant-ui/react";
import type { ViewMessage } from "@/lib/chat/store";
import type { Lang, MessageMeta } from "@/lib/contract";
import { fmtTime } from "@/lib/format";
import { t } from "@/lib/i18n";
import { Chips } from "./Chips";
import { ConfirmCard } from "./ConfirmCard";
import { Receipt } from "./Receipt";

export interface MessageCustom { role: "customer" | "assistant" | "agent" | "system"; text: string; meta?: MessageMeta | null;
  author?: string | null; ts?: string; status?: "sending" | "sent" | "provisional" }

const ROLE: Record<ViewMessage["role"], ThreadMessageLike["role"]> = { customer: "user", assistant: "assistant", agent: "assistant", system: "system" };

export function toThreadMessage(m: ViewMessage): ThreadMessageLike {
  return { id: m.id, role: ROLE[m.role], content: [{ type: "text", text: m.text }], createdAt: new Date(m.ts),
    metadata: { custom: { role: m.role, text: m.text, meta: m.meta, author: m.author, ts: m.ts, status: m.status } satisfies MessageCustom } };
}

export function customerText(text: string, lang: Lang): string {
  return text.startsWith("confirm:") ? t(lang).confirm : text;
}

export function systemLine(c: Pick<MessageCustom, "text" | "meta" | "author">, lang: Lang): string {
  const d = t(lang);
  if (c.meta?.error_code) return c.text;
  if (c.meta?.control === "agent") return d.backToAssistant;
  if (c.meta?.control) return d.agentJoined(c.meta.agent_name ?? c.author ?? "");
  return c.text;
}

export function MessageView({ lang, busy, latestAssistantId, onSend }:
  { lang: Lang; busy: boolean; latestAssistantId?: string; onSend: (text: string) => void }) {
  const id = useAuiState((s) => s.message.id);
  const custom = useAuiState((s) => (s.message.metadata as unknown as { custom?: MessageCustom }).custom);
  if (!custom) return null;
  const d = t(lang);
  const { role, text, meta } = custom;
  const latest = id === latestAssistantId;
  const time = custom.ts ? fmtTime(custom.ts, lang) : "";
  const stamp = (side: "self-start" | "self-end") => time && <time dateTime={custom.ts} className={`${side} -mt-1 px-1 text-[11px] text-b-muted`}>{time}</time>;
  return (
    // Only rows born in this view animate; their stored copies replace them in place, so nothing flashes twice.
    <MessagePrimitive.Root className={`flex flex-col gap-2 ${custom.status ? "motion-safe:animate-[fade-in_220ms_ease-out]" : ""}`}>
      {role === "customer" && (
        <>
          <p className="max-w-[84%] self-end whitespace-pre-wrap rounded-bubble rounded-br-[4px] bg-b-cobalt px-3.5 py-2.5 text-b-surface">{customerText(text, lang)}</p>
          {stamp("self-end")}
        </>
      )}
      {role === "assistant" && (
        <>
          {text && <p className="max-w-[84%] self-start whitespace-pre-wrap rounded-bubble rounded-bl-[4px] bg-b-mist px-3.5 py-2.5">{text}</p>}
          {text && stamp("self-start")}
          {latest && meta?.awaiting === "clarification" && meta.options?.length ? (
            <Chips options={meta.options} disabled={busy} onPick={onSend} />
          ) : null}
          {latest && meta?.awaiting === "confirmation" && meta.summary ? (
            <ConfirmCard summary={meta.summary} lang={lang} disabled={busy} onConfirm={() => onSend(meta.summary?.card_hash ? `confirm:${meta.summary.card_hash}` : d.confirm)} onChange={() => onSend(d.change)} />
          ) : null}
          {meta?.refs?.map((r) => <Receipt key={r} refId={r} lang={lang} />)}
        </>
      )}
      {role === "agent" && (
        <>
          <span className="ml-1 text-xs font-semibold text-b-leaf">{d.agentLabel(custom.author ?? "")}</span>
          <p className="max-w-[84%] self-start whitespace-pre-wrap rounded-bubble rounded-bl-[4px] bg-b-leaf px-3.5 py-2.5 text-b-surface">{text}</p>
          {stamp("self-start")}
        </>
      )}
      {role === "system" && (
        <p className="self-center rounded-full bg-b-fog px-3 py-1 text-center text-xs text-b-muted">{systemLine(custom, lang)}</p>
      )}
    </MessagePrimitive.Root>
  );
}
