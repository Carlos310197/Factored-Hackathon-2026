"use client";
import { useEffect, useRef, useState } from "react";
import { isDemoMessage } from "@/lib/demo/bridge";
import { SCENARIOS, type Scenario } from "@/lib/demo/scenarios";
import { TraceList } from "../trace/TraceList";
import { HandoffTicker } from "./HandoffTicker";
import { PhoneFrame } from "./PhoneFrame";
import { ScenarioRail } from "./ScenarioRail";
import { SignInPanel, type AuthSteps, type Claims } from "./SignInPanel";

type Act = 1 | 2 | 3;
const ACTS: [Act, string][] = [[1, "Sign in"], [2, "Live conversation"], [3, "Scenarios"]];
const NO_STEPS: AuthSteps = { otp: false, token: false, realtime: false, firstTurn: false };

export function DemoStage() {
  const phone = useRef<HTMLIFrameElement>(null);
  const [act, setAct] = useState<Act>(1);
  const [src, setSrc] = useState("/login?next=/chat&embed=1");
  const [sid, setSid] = useState<string | null>(null);
  const [steps, setSteps] = useState<AuthSteps>(NO_STEPS);
  const [claims, setClaims] = useState<Claims | null>(null);
  const [running, setRunning] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [users, setUsers] = useState<{ username: string; lang: string; scenarios: string[] }[]>([]);
  const [scenario, setScenario] = useState<{ s: Scenario; step: number } | null>(null);

  useEffect(() => {
    void fetch("/api/auth/demo-users").then(async (r) => { if (r.ok) setUsers((await r.json()).data); }).catch(() => undefined);
    const onMsg = (e: MessageEvent) => {
      if (!isDemoMessage(e)) return;
      const m = e.data;
      if (m.type === "demo:auth" && m.step === "otp_verified") setSteps((s) => ({ ...s, otp: true }));
      if (m.type === "demo:auth" && m.step === "token_issued") {
        setSteps((s) => ({ ...s, token: true }));
        void fetch("/api/auth/debug-claims", { cache: "no-store" }).then(async (r) => { if (r.ok) setClaims((await r.json()).data); }).catch(() => undefined);
      }
      if (m.type === "demo:session") { setSid(m.sid); setSteps((s) => ({ ...s, realtime: true })); }
      if (m.type === "demo:turn-start") setRunning(true);
      if (m.type === "demo:turn-reply") {
        setRunning(false); setRefreshKey((k) => k + 1); setSteps((s) => ({ ...s, firstTurn: true }));
        setScenario((sc) => (sc ? { ...sc, step: sc.step + 1 } : sc));
      }
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, []);

  async function startScenario(s: Scenario, username: string) {
    await fetch("/api/auth/logout", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ who: "customer" }) });
    setSid(null); setSteps(NO_STEPS); setClaims(null); setScenario({ s, step: 0 }); setRunning(false);
    const short = s.key === "expired_token" ? "&short=1" : "";
    setSrc(`/login?embed=1&auto=1&user=${encodeURIComponent(username)}${short}&next=/chat&t=${Date.now()}`);
  }
  const prefill = (text: string) => phone.current?.contentWindow?.postMessage({ type: "demo:prefill", text }, window.location.origin);
  const nextStep = scenario ? scenario.s.steps[scenario.step] ?? null : null;

  return (
    <main className="font-staff min-h-dvh min-w-[1280px] bg-c-canvas text-c-ink px-8 py-6">
      <header className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold">LATAM Bank · customer service agent</h1>
        <nav aria-label="Demo acts" className="flex gap-2">
          {ACTS.map(([n, label]) => (
            <button key={n} type="button" aria-current={act === n ? "step" : undefined} onClick={() => setAct(n)}
              className={`rounded-full px-4 py-2 text-sm font-semibold ${act === n ? "bg-c-ink text-c-panel" : "bg-c-panel ring-1 ring-c-line text-c-muted hover:text-c-ink"}`}>
              {`${n} · ${label}${n === 1 && steps.firstTurn ? " ✓" : ""}`}
            </button>
          ))}
        </nav>
      </header>
      <div className={`grid gap-6 items-start ${act === 3 ? "grid-cols-[260px_340px_1fr]" : "grid-cols-[340px_1fr]"}`}>
        {act === 3 && (
          <div>
            <ScenarioRail users={users} onStart={(s, u) => void startScenario(s, u)} activeKey={scenario?.s.key ?? null} nextStep={nextStep} onPrefill={prefill} />
            <HandoffTicker />
          </div>
        )}
        <PhoneFrame ref={phone} src={src} />
        <div className="min-w-0">
          {act === 1 ? <SignInPanel steps={steps} claims={claims} /> : (
            <>
              <h2 className="text-lg font-bold mb-3">Decision trace</h2>
              {sid ? <TraceList sid={sid} mode="demo" refreshKey={refreshKey} running={running} />
                : <p className="text-sm text-c-muted">Sign in on the phone to start a session.</p>}
            </>
          )}
        </div>
      </div>
      <p className="mt-5 text-xs text-c-muted">Demo · labeled test identities · synthetic data (data as of 2026-06-17) · {SCENARIOS.length} scenarios</p>
    </main>
  );
}
