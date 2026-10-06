"use client";
import { AssistantRuntimeProvider, ThreadPrimitive, useExternalStoreRuntime } from "@assistant-ui/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "zustand";
import { api, sessionsApi, syncHistory } from "@/lib/chat/api";
import { createChatStore, uiLang, type ViewMessage } from "@/lib/chat/store";
import { SessionEvent, type Lang } from "@/lib/contract";
import { isDemoMessage, notifyParent } from "@/lib/demo/bridge";
import { t } from "@/lib/i18n";
import { newClientMessageId } from "@/lib/ids";
import { signOut } from "@/lib/signout";
import { useChannel } from "@/lib/realtime/useChannel";
import { AsOfBanner } from "./AsOfBanner";
import { EndedBanner } from "./EndedBanner";
import { CasesPanel } from "./CasesPanel";
import { ExpiredSheet } from "./ExpiredSheet";
import { HistoryDrawer } from "./HistoryDrawer";
import { customerText, MessageView, toThreadMessage } from "./MessageView";

const line = "self-center rounded-full bg-b-fog px-3 py-1 text-center text-xs text-b-muted";

export function ChatScreen({ sid, lang: sessionLang, embed }: { sid: string; lang: Lang; embed: boolean }) {
  const [store] = useState(createChatStore);
  const s = useStore(store);
  const lastReply = s.messages.findLast((m) => m.role === "assistant");
  const replyKey = lastReply?.turn_id ?? lastReply?.id;
  const [manual, setManual] = useState<{ lang: Lang; at?: string } | null>(null);
  const lang = manual && manual.at === replyKey ? manual.lang : uiLang(s.messages, sessionLang);
  const d = t(lang);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const [inFlight, setInFlight] = useState(0);
  const [ctl, setCtl] = useState<{ control: string; agent_name?: string | null } | null>(null);
  const asyncTurn = useRef(false);
  const queue = useRef<Promise<void>>(Promise.resolve());

  const resync = useCallback(() => void syncHistory(store, sid), [sid, store]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const leave = () => void signOut("customer").then(() => router.replace(`/login${embed ? "?next=/chat&embed=1" : ""}`));
  const expire = () => { setHistoryOpen(false); store.getState().expire(); };
  /** /chat is keyed by sid: after /new swaps the cookie, refreshing remounts the chat on the new session. */
  const startNew = async () => {
    const r = await sessionsApi.create();
    if (r.kind === "ok") { setHistoryOpen(false); router.refresh(); return true; }
    if (r.kind === "expired") expire();
    return false;
  };

  useEffect(() => {
    notifyParent({ type: "demo:session", sid });
    resync();
    const onMsg = (e: MessageEvent) => { if (isDemoMessage(e) && e.data.type === "demo:prefill") { setDraft(e.data.text); input.current?.focus(); } };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, [sid, resync]);

  const status = useChannel(`/session/${sid}`, (payload) => {
    const ev = SessionEvent.safeParse(payload);
    if (!ev.success) return;
    if (ev.data.type === "control") setCtl({ control: ev.data.control, agent_name: ev.data.agent_name });
    store.getState().applyEvent(ev.data);
  }, { as: "customer", onResync: resync });

  useEffect(() => { if (status === "live") notifyParent({ type: "demo:realtime" }); }, [status]);

  const send = useCallback((text: string, clientId = newClientMessageId()) => {
    const body = text.trim();
    if (!body) return;
    store.getState().sendOptimistic(clientId, body);
    setInFlight((n) => n + 1);
    queue.current = queue.current.then(async () => {
      notifyParent({ type: "demo:turn-start", text: customerText(body, lang) });
      const r = await api.send(body, clientId);
      if (r.kind === "reply") { store.getState().applyReply(clientId, r.reply); notifyParent({ type: "demo:turn-reply", turn_id: r.reply.turn_id }); resync(); }
      else if (r.kind === "expired") store.getState().expire();
      else if (r.kind === "ended") { store.getState().fail(clientId); store.getState().end(); }
      else if (r.kind === "error") store.getState().fail(clientId);
      else { asyncTurn.current = true; resync(); }
    }).finally(() => setInFlight((n) => n - 1));
  }, [store, resync, lang]);

  useEffect(() => {
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
    convertMessage: toThreadMessage,
    onNew: async (m) => { send(m.content.map((p) => (p.type === "text" ? p.text : "")).join("")); },
  });

  // A session can hand off twice: judge hand-off lines only against what came after the latest assistant message.
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
        <div inert={s.expired || historyOpen} className="relative flex h-dvh w-full max-w-md flex-col overflow-hidden bg-b-surface sm:my-6 sm:h-[calc(100dvh-3rem)] sm:rounded-card sm:border sm:border-b-line">
          {!embed && (
            <header className="relative flex shrink-0 items-center justify-between overflow-hidden bg-b-cobalt px-5 py-4 text-b-surface">
              <span aria-hidden className="absolute -right-6 -top-10 size-24 rounded-full bg-b-sun" />
              <span aria-hidden className="absolute -bottom-10 right-14 size-20 rounded-full bg-b-leaf" />
              <h1 className="relative text-lg font-extrabold tracking-tight">{d.bank}</h1>
              <span className="relative flex items-center gap-2">
                <button type="button" aria-label={d.history} aria-haspopup="dialog" onClick={() => setHistoryOpen(true)}
                  className="flex size-11 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-surface">
                  <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2" /></svg>
                </button>
                <CasesPanel lang={lang} />
                <button type="button" aria-label={`${lang.toUpperCase()}, ${d.switchLang}`} onClick={() => setManual({ lang: lang === "es" ? "pt" : "es", at: replyKey })}
                  className="min-h-11 min-w-11 rounded-full px-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-surface">
                  <span className="rounded-full bg-b-surface px-2.5 py-0.5 text-xs font-bold text-b-ink">{lang.toUpperCase()}</span>
                </button>
                <button type="button" onClick={leave}
                  className="min-h-11 rounded-full bg-b-surface px-4 text-sm font-bold text-b-cobalt focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-surface">{d.signOut}</button>
              </span>
            </header>
          )}
          <AsOfBanner date={asOf} lang={lang} />
          {status === "reconnecting" && <p role="status" className="bg-b-fog px-4 py-1.5 text-center text-xs text-b-muted">{d.reconnecting}</p>}

          <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
            <ThreadPrimitive.Viewport autoScroll aria-live="polite" className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
              <ThreadPrimitive.Messages>
                {() => <MessageView lang={lang} busy={busy} latestAssistantId={latestAssistantId} onSend={send} />}
              </ThreadPrimitive.Messages>
              {ctlLine && <p className={`${line} motion-safe:animate-[fade-in_220ms_ease-out]`}>{ctlLine}</p>}
              {handedOver && <p className={line}>{d.humanWillContinue}</p>}
              {(busy || s.running) && (
                <p role="status" className="inline-flex min-h-11 min-w-[4.5rem] items-center gap-2 self-start rounded-bubble rounded-bl-[4px] bg-b-mist px-3.5 py-2.5 text-b-muted motion-safe:animate-[fade-in_220ms_ease-out]">
                  <span aria-hidden className="flex gap-1">
                    {[0, 160, 320].map((ms) => <span key={ms} style={{ animationDelay: `${ms}ms` }} className="size-1.5 rounded-full bg-b-muted motion-safe:animate-[dot_1.2s_ease-in-out_infinite]" />)}
                  </span>
                  {s.progress ? <span key={s.progress} className="text-sm motion-safe:animate-[fade-in_200ms_ease-out]">{d.stage[s.progress]}</span> : <span className="sr-only">{d.typing}</span>}
                </p>
              )}
            </ThreadPrimitive.Viewport>
          </ThreadPrimitive.Root>

          {s.ended && <EndedBanner lang={lang} onNew={startNew} onSignOut={leave} />}
          {!s.ended && s.failed && (
            <div role="alert" className="motion-safe:animate-[fade-in_220ms_ease-out] mx-3 mb-2 flex items-center justify-between gap-3 rounded-bubble bg-b-sun-tint px-4 py-2.5 text-sm">
              <span>{d.sendFailed}</span>
              <button type="button" className="min-h-11 rounded-full px-3 font-bold text-b-cobalt focus-visible:outline-2 focus-visible:outline-b-cobalt"
                onClick={() => { const f = s.failed!; send(f.text, f.clientId); }}>{d.retry}</button>
            </div>
          )}
          {!s.ended && <form className="mx-3 mb-3 flex shrink-0 items-center gap-2 rounded-full bg-b-fog py-1.5 pl-4 pr-1.5 ring-b-cobalt/30 transition-shadow focus-within:ring-2"
            onSubmit={(e) => { e.preventDefault(); const text = draft; setDraft(""); send(text); }}>
            <input ref={input} aria-label={d.placeholder} placeholder={d.placeholder} value={draft} onChange={(e) => setDraft(e.target.value)}
              maxLength={2000} className="min-w-0 flex-1 bg-transparent py-2 text-base text-b-ink placeholder:text-b-muted focus-visible:outline-none" />
            <button type="submit" disabled={!draft.trim()} aria-label={d.send}
              className="flex size-11 items-center justify-center rounded-full bg-b-cobalt text-b-surface transition-[transform,opacity] duration-150 active:scale-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-cobalt disabled:opacity-40">
              <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
            </button>
          </form>}
        </div>
        {historyOpen && <HistoryDrawer lang={lang} ended={s.ended} onClose={() => setHistoryOpen(false)}
          onEnded={() => { setHistoryOpen(false); store.getState().end(); }} onNew={startNew} onExpired={expire} />}
        {s.expired && <ExpiredSheet lang={lang} embed={embed} />}
      </main>
    </AssistantRuntimeProvider>
  );
}
