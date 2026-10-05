import { useState } from "react";

export type AuthSteps = { otp: boolean; token: boolean; realtime: boolean; firstTurn: boolean };
export type Claims = { sub: string; sid: string; lang: string; scopes: string[]; exp: number };

export function SignInPanel({ steps, claims }: { steps: AuthSteps; claims: Claims | null }) {
  const [now] = useState(() => Date.now()); // minutes left as of when the claims were shown
  const mins = claims ? Math.max(0, Math.round((claims.exp * 1000 - now) / 60_000)) : null;
  const items: [keyof AuthSteps, string, React.ReactNode][] = [
    ["otp", "OTP verified", <span key="b"> by the identity service</span>],
    ["token", "Access token issued", claims ? (
      <dl key="b" className="grid grid-cols-[110px_1fr] gap-x-3 gap-y-1 mt-2 text-sm">
        <dt className="text-c-muted">customer</dt><dd>{`${claims.sub} (sub)`}</dd>
        <dt className="text-c-muted">session</dt><dd>{`${claims.sid} (sid)`}</dd>
        <dt className="text-c-muted">language</dt><dd>{claims.lang}</dd>
        <dt className="text-c-muted">can do</dt><dd>{[...claims.scopes].sort().reverse().join(" · ")}</dd>
        <dt className="text-c-muted">expires</dt><dd>{`in ${mins} min`}</dd>
      </dl>) : <span key="b"> · RS256, signed by our identity service</span>],
    ["realtime", "Realtime token issued", <span key="b"> · subscribe-only, this session&apos;s channel only</span>],
    ["firstTurn", "First message", <span key="b"> · AgentCore&apos;s authorizer checks the token, then the agent re-checks it and takes the customer id from it, never from the message</span>],
  ];
  return (
    <section>
      <h2 className="text-lg font-bold mb-3">What just happened</h2>
      <ol className="flex flex-col gap-2.5">
        {items.map(([k, title, body], i) => (
          <li key={k} data-done={steps[k]} className={`bg-c-panel rounded-[var(--radius-panel)] ring-1 ring-c-line px-4 py-3.5 grid grid-cols-[28px_1fr_auto] gap-3 transition-opacity ${steps[k] ? "" : "opacity-45"}`}>
            <span className={`size-7 rounded-full text-sm font-bold text-c-panel flex items-center justify-center ${steps[k] ? "bg-c-pass" : "bg-c-below"}`}>{i + 1}</span>
            <div className="text-[15px]"><b>{title}</b>{body}</div>
            <span className="text-sm font-bold">{steps[k] ? <span className="text-c-pass">✓</span> : <span className="text-c-muted">waiting</span>}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
