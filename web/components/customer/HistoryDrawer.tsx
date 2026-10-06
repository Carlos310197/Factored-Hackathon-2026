"use client";
import { AssistantRuntimeProvider, ThreadPrimitive, useExternalStoreRuntime } from "@assistant-ui/react";
import { useEffect, useRef, useState } from "react";
import { api, sessionsApi } from "@/lib/chat/api";
import type { ChatMessage, Lang, SessionSummary } from "@/lib/contract";
import { fmtDate, fmtTime } from "@/lib/format";
import { t } from "@/lib/i18n";
import { MessageView, toThreadMessage } from "./MessageView";

const pill = "min-h-11 rounded-full px-4 text-sm font-bold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-cobalt";
const primary = `${pill} bg-b-cobalt text-b-surface`;
const quiet = `${pill} border-[1.5px] border-b-line bg-b-surface text-b-ink`;
const tag = "rounded-full px-2 py-0.5 text-[11px] font-bold";

/** A past conversation, read-only: the same message rendering as the chat, with no composer and no live chips/cards. */
function Transcript({ messages, lang }: { messages: ChatMessage[]; lang: Lang }) {
  const runtime = useExternalStoreRuntime<ChatMessage>({ messages, isRunning: false, convertMessage: toThreadMessage, onNew: async () => {} });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
        <ThreadPrimitive.Viewport className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          <ThreadPrimitive.Messages>{() => <MessageView lang={lang} busy latestAssistantId={undefined} onSend={() => {}} />}</ThreadPrimitive.Messages>
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}

/** "Conversaciones": the customer's own conversations. Past ones open read-only and can be hidden (never deleted);
 *  the current one can be ended, or ended and replaced by a new one. */
export function HistoryDrawer({ lang, ended, onClose, onEnded, onNew, onExpired }: {
  lang: Lang; ended: boolean; onClose: () => void; onEnded: () => void; onNew: () => Promise<boolean>; onExpired: () => void;
}) {
  const d = t(lang);
  const [list, setList] = useState<SessionSummary[] | null>(null);
  const [viewing, setViewing] = useState<{ s: SessionSummary; messages: ChatMessage[] | null } | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);  // a session id to hide, or "end"
  const [failed, setFailed] = useState(false);
  const closeBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {  // focus moves in, and back to whatever opened the drawer when it closes
    const opener = document.activeElement as HTMLElement | null;
    closeBtn.current?.focus();
    return () => opener?.focus();
  }, []);

  const expired = useRef(onExpired);
  const close = useRef(onClose);
  useEffect(() => { expired.current = onExpired; close.current = onClose; });
  useEffect(() => {  // Escape closes even when focus fell to <body> (e.g. after "Volver" unmounts)
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close.current(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {  // loaded once per opening; the parent's callback may change identity on every render
    let live = true;
    void sessionsApi.list().then((r) => {
      if (!live) return;
      if (r.kind === "ok") setList(r.data);
      else if (r.kind === "expired") expired.current();
      else setFailed(true);
    });
    return () => { live = false; };
  }, []);

  const settle = (r: { kind: string }, ok: () => void) => {
    if (r.kind === "ok") { setFailed(false); ok(); }
    else if (r.kind === "expired") onExpired();
    else setFailed(true);
  };
  const open = async (s: SessionSummary) => {
    if (s.current) return onClose();
    setViewing({ s, messages: null });
    const r = await api.history(s.session_id);
    settle(r, () => r.kind === "ok" && setViewing({ s, messages: r.messages }));
  };
  const hide = async (sid: string) =>
    settle(await sessionsApi.hide(sid), () => { setList((l) => l?.filter((x) => x.session_id !== sid) ?? l); setConfirm(null); });
  const end = async () => settle(await sessionsApi.end(), onEnded);
  const startNew = async () => setFailed(!(await onNew()));
  const when = (iso: string) => `${fmtDate(iso, lang)} · ${fmtTime(iso, lang)}`;

  return (
    <div className="fixed inset-0 z-10 flex justify-center bg-b-ink/40" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby="history-title"
        className="font-customer flex h-full w-full max-w-md flex-col bg-b-surface text-b-ink motion-safe:animate-[fade-in_180ms_ease-out]">
        <header className="flex shrink-0 items-center justify-between gap-2 border-b border-b-line px-4 py-3">
          {viewing ? (
            <button type="button" onClick={() => { setViewing(null); closeBtn.current?.focus(); }} className={`${quiet} border-0 px-2`}><span aria-hidden>← </span>{d.back}</button>
          ) : <h2 id="history-title" className="text-lg font-extrabold">{d.history}</h2>}
          {viewing && <h2 id="history-title" className="sr-only">{d.history}</h2>}
          <button ref={closeBtn} type="button" aria-label={d.close} onClick={onClose} className={`${pill} flex w-11 items-center justify-center px-0 text-b-muted`}>
            <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </header>

        {failed && <p role="alert" className="mx-4 mt-3 rounded-bubble bg-b-sun-tint px-4 py-2 text-sm">{d.actionFailed}</p>}

        {viewing ? (
          <>
            <p className="shrink-0 bg-b-fog px-4 py-2 text-center text-xs font-semibold text-b-muted">{d.readOnly}</p>
            {viewing.messages ? <Transcript messages={viewing.messages} lang={lang} />
              : <p role="status" className="p-6 text-center text-sm text-b-muted">{d.loading}</p>}
          </>
        ) : (
          <>
            {!list && !failed && <p role="status" className="p-6 text-center text-sm text-b-muted">{d.loading}</p>}
            <ul className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-3">
              {list?.map((s) => (
                <li key={s.session_id} className="rounded-card border border-b-line">
                  <button type="button" onClick={() => void open(s)} className="flex w-full flex-col items-start gap-1 rounded-card px-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-b-cobalt">
                    <span className="flex flex-wrap items-center gap-1.5 text-xs text-b-muted">
                      <time dateTime={s.created_at}>{when(s.created_at)}</time>
                      {s.current && <span className={`${tag} bg-b-cobalt text-b-surface`}>{d.currentTag}</span>}
                      {s.ended && <span className={`${tag} bg-b-fog text-b-muted`}>{d.endedTag}</span>}
                    </span>
                    <span className={`line-clamp-2 text-sm ${s.preview ? "font-semibold" : "italic text-b-muted"}`}>{s.preview ?? d.noMessages}</span>
                  </button>
                  {!s.current && (confirm === s.session_id ? (
                    <div className="flex flex-wrap items-center gap-2 px-4 pb-3">
                      <p className="w-full text-xs text-b-muted">{d.hideConfirm}</p>
                      <button type="button" onClick={() => void hide(s.session_id)} className={primary}>{d.hideYes}</button>
                      <button type="button" onClick={() => setConfirm(null)} className={quiet}>{d.cancel}</button>
                    </div>
                  ) : (
                    <button type="button" onClick={() => setConfirm(s.session_id)} className="mx-2 mb-1 min-h-11 rounded-full px-2 text-xs font-bold text-b-cobalt focus-visible:outline-2 focus-visible:outline-b-cobalt">{d.hide}</button>
                  ))}
                </li>
              ))}
            </ul>
            <footer className="flex shrink-0 flex-col gap-2 border-t border-b-line p-3">
              {confirm === "end" ? (
                <>
                  <p className="text-sm">{d.endConfirm}</p>
                  <span className="flex gap-2">
                    <button type="button" onClick={() => void end()} className={primary}>{d.endYes}</button>
                    <button type="button" onClick={() => setConfirm(null)} className={quiet}>{d.cancel}</button>
                  </span>
                </>
              ) : (
                <>
                  <button type="button" onClick={() => void startNew()} className={`${pill} bg-b-leaf text-b-surface`}>{d.newConversation}</button>
                  {!ended && <button type="button" onClick={() => setConfirm("end")} className={quiet}>{d.endConversation}</button>}
                </>
              )}
            </footer>
          </>
        )}
      </div>
    </div>
  );
}
