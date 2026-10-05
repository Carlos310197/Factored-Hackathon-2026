"use client";
import { useEffect, useRef, useState } from "react";
import { RESOLUTION_CODES, type HandoffPacket, type ResolutionCode } from "@/lib/contract";
import { fmtDate } from "@/lib/format";
import { ACTION_LABEL, PRIORITY_WORD, allowedActions, type CaseAction } from "@/lib/staff/actions";

const OUTCOME: Record<ResolutionCode, string> = { resolved_by_agent: "Resolved by agent", dispute_filed_manually: "Dispute filed manually",
  no_action_needed: "No action needed", referred_to_phone: "Referred to phone" };
const STATUS_WORD = { open: "open", claimed: "claimed", in_takeover: "in takeover", returned: "returned to assistant", resolved: "resolved" } as const;
const MARK = { critical: "bg-c-alert", high: "bg-c-warn", medium: "bg-c-below" } as const;
const opened = (iso: string) => new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }).format(new Date(iso)) + " UTC";
const btn = "inline-flex items-center gap-1.5 rounded-control px-3.5 py-2 text-xs font-bold transition-opacity disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-c-signal";
const field = "border border-c-line rounded-control px-2.5 py-2 bg-c-panel focus-visible:outline-2 focus-visible:outline-c-signal";

export function CaseHeader({ packet, control, me, onAction, pending = null }: { packet: HandoffPacket; control: string; me: { sub: string; name: string };
  onAction: (a: CaseAction, body?: { code: ResolutionCode; note: string }) => void; pending?: CaseAction | null }) {
  const [resolving, setResolving] = useState(false);
  const [code, setCode] = useState<ResolutionCode>("resolved_by_agent");
  const [note, setNote] = useState("");
  const opener = useRef<HTMLButtonElement>(null);
  const first = useRef<HTMLSelectElement>(null);
  const actions = allowedActions(packet, me.sub);
  const heldByOther = packet.claimed_by && packet.claimed_by !== me.sub && packet.status !== "resolved";
  const dlg = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const d = dlg.current;
    if (!resolving || !d) return;
    // native modal: focus trap, Esc (cancel event) and inert background; jsdom lacks showModal
    if (typeof d.showModal === "function") d.showModal(); else d.setAttribute("open", "");
    first.current?.focus();
  }, [resolving]);
  // close the modal first: while it is open everything outside is inert and focus() would do nothing
  const shut = () => { dlg.current?.close?.(); setResolving(false); };
  const close = () => { shut(); opener.current?.focus(); };
  const openResolve = () => { setCode("resolved_by_agent"); setNote(""); setResolving(true); };
  const meta = [`Customer ${packet.customer_id}`, packet.language === "es" ? "Spanish" : "Portuguese", `data as of ${fmtDate(packet.data_as_of, "es")}`,
    `session ${packet.session_id}`, `opened ${opened(packet.created_at)}`];
  return (
    <header className="bg-c-panel ring-1 ring-c-line rounded-panel px-4 py-3.5 flex justify-between items-start gap-4">
      <div className="min-w-0">
        <h1 ref={title} tabIndex={-1} className="text-lg font-bold outline-none flex items-center gap-2.5 flex-wrap">
          {packet.handoff_id}
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-bold ${packet.priority === "critical" ? "bg-c-alert-tint text-c-alert" : "bg-c-track text-c-ink"}`}>
            <span className={`size-2 rounded-[2px] ${MARK[packet.priority]}`} aria-hidden />
            <span>{PRIORITY_WORD[packet.priority]} · {STATUS_WORD[packet.status]}</span>
          </span>
        </h1>
        <p className="text-xs text-c-muted mt-1 leading-relaxed">
          {meta.join(" · ")}
          {heldByOther ? ` · held by ${packet.claimed_by}` : ""}{control.startsWith("human:") ? ` · chat held by ${control.slice(6)}` : ""}
        </p>
      </div>
      <div className="flex gap-1.5 shrink-0">
        {actions.filter((a) => a !== "resolve").map((a, i) => (
          <button key={a} onClick={() => onAction(a, undefined)} disabled={pending !== null} aria-busy={pending === a}
            className={`${btn} ${i === 0 ? "bg-c-signal text-c-panel hover:opacity-90" : "bg-c-track hover:bg-c-line"}`}>
            {pending === a && <span aria-hidden className="size-3 rounded-full border-2 border-current border-r-transparent motion-safe:animate-spin" />}
            {ACTION_LABEL[a]}</button>
        ))}
        {actions.includes("resolve") && (
          <button ref={opener} onClick={openResolve} disabled={pending !== null} aria-busy={pending === "resolve"} className={`${btn} bg-c-track hover:bg-c-line`}>{ACTION_LABEL.resolve}</button>
        )}
      </div>
      {resolving && (
        <dialog ref={dlg} aria-labelledby="resolve-title" onCancel={(e) => { e.preventDefault(); close(); }}
          className="m-auto bg-c-panel text-c-ink ring-1 ring-c-line rounded-panel p-5 w-[26rem] backdrop:bg-c-ink/40">
          <form className="flex flex-col gap-3.5"
            onSubmit={(e) => { e.preventDefault(); shut(); title.current?.focus(); onAction("resolve", { code, note }); }}>
            <h2 id="resolve-title" className="font-bold">Resolve {packet.handoff_id}</h2>
            <label className="flex flex-col gap-1 text-sm font-semibold">Outcome
              <select ref={first} value={code} onChange={(e) => setCode(e.target.value as ResolutionCode)} className={`${field} font-normal`}>
                {RESOLUTION_CODES.map((c) => <option key={c} value={c}>{OUTCOME[c]}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold">Note
              <textarea value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} className={`${field} font-normal h-24 resize-none`} />
            </label>
            <p className="text-xs text-c-muted tabular-nums -mt-2.5 text-right" aria-hidden>{note.length}/500</p>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={close} className={`${btn} bg-c-track hover:bg-c-line`}>Cancel</button>
              <button type="submit" className={`${btn} bg-c-signal text-c-panel hover:opacity-90`}>Resolve case</button>
            </div>
          </form>
        </dialog>
      )}
    </header>
  );
}
