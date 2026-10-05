"use client";
import { SCENARIOS, type Scenario } from "@/lib/demo/scenarios";

type U = { username: string; lang: string; scenarios: string[] };

export function ScenarioRail({ users, onStart, activeKey, nextStep, onPrefill }:
  { users: U[]; onStart: (s: Scenario, username: string) => void; activeKey: string | null; nextStep: string | null; onPrefill: (t: string) => void }) {
  const note = SCENARIOS.find((s) => s.key === activeKey)?.note;
  return (
    <section className="bg-c-panel rounded-[var(--radius-panel)] ring-1 ring-c-line p-3 text-sm">
      <h2 className="font-bold mb-2">Scenarios</h2>
      {SCENARIOS.map((s) => {
        const user = users.find((u) => u.scenarios.includes(s.key));
        return (
          <button key={s.key} type="button" disabled={!user} onClick={() => user && onStart(s, user.username)}
            aria-current={activeKey === s.key ? "true" : undefined}
            className={`block w-full text-left rounded-[var(--radius-control)] px-2.5 py-2 mb-1.5 font-semibold disabled:opacity-50 disabled:cursor-not-allowed
              ${activeKey === s.key ? "bg-c-signal-tint shadow-[inset_3px_0_0_var(--color-c-signal)]" : "bg-c-canvas hover:bg-c-track"}`}>
            {s.label}
            <small className="block font-normal text-c-muted text-xs mt-0.5">{user ? `“${s.steps[0]}”` : "No demo identity has data for this"}</small>
          </button>
        );
      })}
      {activeKey && nextStep && (
        <div className="mt-2 border-t border-c-track pt-2.5">
          <p className="font-bold mb-1.5">Next message</p>
          <button type="button" aria-label={`Put in composer: ${nextStep}`} onClick={() => onPrefill(nextStep)}
            className="w-full text-left rounded-[var(--radius-control)] bg-c-signal text-c-panel px-2.5 py-2 font-semibold">{nextStep}</button>
          {note && <p className="text-c-muted mt-1.5 text-xs">{note}</p>}
        </div>
      )}
    </section>
  );
}
