"use client";
import { AssistantRuntimeProvider, ThreadPrimitive, useExternalStoreRuntime, type ThreadMessageLike } from "@assistant-ui/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "zustand";
import { api, syncHistory } from "@/lib/chat/api";
import { createChatStore, type ViewMessage } from "@/lib/chat/store";
import { SessionEvent, type Lang } from "@/lib/contract";
import { isDemoMessage, notifyParent } from "@/lib/demo/bridge";
import { t } from "@/lib/i18n";
import { newClientMessageId } from "@/lib/ids";
import { useChannel } from "@/lib/realtime/useChannel";
import { AsOfBanner } from "./AsOfBanner";
import { ExpiredSheet } from "./ExpiredSheet";
import { MessageView, type MessageCustom } from "./MessageView";

const ROLE: Record<ViewMessage["role"], ThreadMessageLike["role"]> = { customer: "user", assistant: "assistant", agent: "assistant", system: "system" };
const line = "self-center rounded-full bg-b-fog px-3 py-1 text-center text-xs text-b-muted";

export function ChatScreen({ sid, lang, embed }: { sid: string; lang: Lang; embed: boolean }) {
  const [store] = useState(createChatStore);
  const s = useStore(store);
  const d = t(lang);
  const [draft, setDraft] = useState("");
  const [inFlight, setInFlight] = useState(0);
  const [ctl, setCtl] = useState<{ control: string; agent_name?: string | null } | null>(null);
  const asyncTurn = useRef(false);
  const queue = useRef<Promise<void>>(Promise.resolve());

  const resync = useCallback(() => void syncHistory(store, sid), [sid, store]);

  useEffect(() => {
    notifyParent({ type: "demo:session", sid });
    resync();
    const onMsg = (e: MessageEvent) => { if (isDemoMessage(e) && e.data.type === "demo:prefill") setDraft(e.data.text); };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, [sid, resync]);

  const status = useChannel(`/session/${sid}`, (payload) => {
    const ev = SessionEvent.safeParse(payload);
    if (!ev.success) return;
    if (ev.data.type === "control") setCtl({ control: ev.data.control, agent_name: ev.data.agent_name });
    store.getState().applyEvent(ev.data);
  }, { as: "customer", onResync: resync });

  useEffect(() => { if (status === "live") notifyParent({ type: "demo:realtime" }); }, [status]); // the subscribe-only token is in use

  /** The composer never locks: each message shows at once and its turn runs after the previous one (ordered queue). */
  const send = useCallback((text: string, clientId = newClientMessageId()) => {
    const body = text.trim();
    if (!body) return;
    store.getState().sendOptimistic(clientId, body);
    setInFlight((n) => n + 1);
    queue.current = queue.current.then(async () => {
      notifyParent({ type: "demo:turn-start", text: body });
      const r = await api.send(body, clientId);
      if (r.kind === "reply") { store.getState().applyReply(clientId, r.reply); notifyParent({ type: "demo:turn-reply", turn_id: r.reply.turn_id }); resync(); }
      else if (r.kind === "expired") store.getState().expire();
      else if (r.kind === "error") store.getState().fail(clientId);
      else { asyncTurn.current = true; resync(); }  // 202: the reply arrives by push or history
    }).finally(() => setInFlight((n) => n - 1));
  }, [store, resync]);

  useEffect(() => {  // 202 path: the turn ended when running cleared by a pushed reply or error line
    if (s.running || !asyncTurn.current) return;
    asyncTurn.current = false;
    notifyParent({ type: "demo:turn-reply", turn_id: [...s.messages].reverse().find((m) => m.role === "assistant")?.turn_id ?? null });
  }, [s.running, s.messages]);

  const busy = inFlight > 0;
  const latestAssistantId = [...s.messages].reverse().find((m) => m.role === "assistant")?.id;
  const asOf = [...s.messages].reverse().find((m) => m.meta?.data_as_of)?.meta?.data_as_of ?? null;
  const runtime = useExternalStoreRuntime<ViewMessage>({
    messages: s.messages,
    isRunning: busy || s.running,
    convertMessage: (m) => ({ id: m.id, role: ROLE[m.role], content: [{ type: "text", text: m.text }], createdAt: new Date(m.ts),
      metadata: { custom: { role: m.role, text: m.text, meta: m.meta, author: m.author, status: m.status } satisfies MessageCustom } }),
    onNew: async (m) => { send(m.content.map((p) => (p.type === "text" ? p.text : "")).join("")); },
  });

  // Hand-off lines are judged against what came after the latest assistant message (a session can hand off twice).
  const lastAsst = s.messages.findLastIndex((m) => m.role === "assistant");
  const controlMsgs = s.messages.filter((m) => m.role === "system" && m.meta?.control);
  const lastControl = controlMsgs.at(-1)?.meta?.control;
  const ctlLine = ctl && lastControl !== ctl.control
    ? (ctl.control === "agent" ? d.backToAssistant : d.agentJoined(ctl.agent_name ?? "")) : null;
  const controlAfterAsst = s.messages.some((m, i) => i > lastAsst && m.role === "system" && m.meta?.control);
  const handedOver = s.awaiting === "human" && !controlAfterAsst && !ctlLine;

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <main className="font-customer flex min-h-dvh justify-center bg-b-fog text-b-ink">
        <div inert={s.expired} className="relative flex h-dvh w-full max-w-md flex-col overflow-hidden bg-b-surface sm:my-6 sm:h-[calc(100dvh-3rem)] sm:rounded-card sm:border sm:border-b-line">
          {!embed && (
            <header className="relative flex shrink-0 items-center justify-between overflow-hidden bg-b-cobalt px-5 py-4 text-b-surface">
              <span aria-hidden className="absolute -right-6 -top-10 size-24 rounded-full bg-b-sun" />
              <span aria-hidden className="absolute -bottom-10 right-14 size-20 rounded-full bg-b-leaf" />
              <h1 className="relative text-lg font-extrabold tracking-tight">{d.bank}</h1>
              <span className="relative rounded-full bg-b-surface px-2.5 py-0.5 text-xs font-bold text-b-ink">{lang.toUpperCase()}</span>
            </header>
          )}
          <AsOfBanner date={asOf} lang={lang} />
          {status === "reconnecting" && <p role="status" className="bg-b-fog px-4 py-1.5 text-center text-xs text-b-muted">{d.reconnecting}</p>}

          <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
            <ThreadPrimitive.Viewport autoScroll aria-live="polite" className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
              <ThreadPrimitive.Messages>
                {() => <MessageView lang={lang} busy={busy} latestAssistantId={latestAssistantId} onSend={send} />}
              </ThreadPrimitive.Messages>
              {ctlLine && <p className={line}>{ctlLine}</p>}
              {handedOver && <p className={line}>{d.humanWillContinue}</p>}
              {(busy || s.running) && (
                <p role="status" className="self-start rounded-bubble rounded-bl-[4px] bg-b-mist px-3.5 py-2.5 tracking-[3px] text-b-muted">
                  <span aria-hidden>•••</span><span className="sr-only">{d.typing}</span>
                </p>
              )}
            </ThreadPrimitive.Viewport>
          </ThreadPrimitive.Root>

          {s.failed && (
            <div role="alert" className="mx-3 mb-2 flex items-center justify-between gap-3 rounded-bubble bg-b-sun-tint px-4 py-2.5 text-sm">
              <span>{d.sendFailed}</span>
              <button type="button" className="min-h-11 rounded-full px-3 font-bold text-b-cobalt focus-visible:outline-2 focus-visible:outline-b-cobalt"
                onClick={() => { const f = s.failed!; send(f.text, f.clientId); }}>{d.retry}</button>
            </div>
          )}
          <form className="mx-3 mb-3 flex shrink-0 items-center gap-2 rounded-full bg-b-fog py-1.5 pl-4 pr-1.5"
            onSubmit={(e) => { e.preventDefault(); const text = draft; setDraft(""); send(text); }}>
            <input aria-label={d.placeholder} placeholder={d.placeholder} value={draft} onChange={(e) => setDraft(e.target.value)}
              maxLength={2000} className="min-w-0 flex-1 bg-transparent py-2 text-base text-b-ink placeholder:text-b-muted focus-visible:outline-none" />
            <button type="submit" disabled={!draft.trim()} aria-label={d.send}
              className="flex size-11 items-center justify-center rounded-full bg-b-cobalt text-lg font-bold text-b-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-cobalt disabled:opacity-40">
              <span aria-hidden>➤</span>
            </button>
          </form>
        </div>
        {s.expired && <ExpiredSheet lang={lang} embed={embed} />}
      </main>
    </AssistantRuntimeProvider>
  );
}
