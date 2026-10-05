"use client";
import { MessagePrimitive, useAuiState } from "@assistant-ui/react";
import type { Lang, MessageMeta } from "@/lib/contract";
import { t } from "@/lib/i18n";
import { Chips } from "./Chips";
import { ConfirmCard } from "./ConfirmCard";
import { Receipt } from "./Receipt";

export interface MessageCustom { role: "customer" | "assistant" | "agent" | "system"; text: string; meta?: MessageMeta | null;
  author?: string | null; status?: "sending" | "provisional" }

/** Control lines come from the system message's meta (takeover/return), never from its stored text. */
export function systemLine(c: Pick<MessageCustom, "text" | "meta" | "author">, lang: Lang): string {
  const d = t(lang);
  if (c.meta?.error_code) return c.text;  // async agent failure: shown as a plain line, no control change
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
  return (
    <MessagePrimitive.Root className="flex flex-col gap-2">
      {role === "customer" && (
        <p className={`max-w-[84%] self-end whitespace-pre-wrap rounded-bubble rounded-br-[4px] bg-b-cobalt px-3.5 py-2.5 text-b-surface ${custom.status === "sending" ? "opacity-80" : ""}`}>{text}</p>
      )}
      {role === "assistant" && (
        <>
          {text && <p className="max-w-[84%] self-start whitespace-pre-wrap rounded-bubble rounded-bl-[4px] bg-b-mist px-3.5 py-2.5">{text}</p>}
          {latest && meta?.awaiting === "clarification" && meta.options?.length ? (
            <Chips options={meta.options} disabled={busy} onPick={onSend} />
          ) : null}
          {latest && meta?.awaiting === "confirmation" && meta.summary ? (
            <ConfirmCard summary={meta.summary} lang={lang} disabled={busy} onConfirm={() => onSend(d.confirm)} onChange={() => onSend(d.change)} />
          ) : null}
          {meta?.refs?.map((r) => <Receipt key={r} refId={r} lang={lang} />)}
        </>
      )}
      {role === "agent" && (
        <>
          <span className="ml-1 text-xs font-semibold text-b-leaf">{d.agentLabel(custom.author ?? "")}</span>
          <p className="max-w-[84%] self-start whitespace-pre-wrap rounded-bubble rounded-bl-[4px] bg-b-leaf px-3.5 py-2.5 text-b-surface">{text}</p>
        </>
      )}
      {role === "system" && (
        <p className="self-center rounded-full bg-b-fog px-3 py-1 text-center text-xs text-b-muted">{systemLine(custom, lang)}</p>
      )}
    </MessagePrimitive.Root>
  );
}
