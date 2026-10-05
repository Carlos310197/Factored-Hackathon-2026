"use client";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { Lang } from "@/lib/contract";
import { notifyParent } from "@/lib/demo/bridge";
import { t } from "@/lib/i18n";

type DemoUser = { username: string; demo_password: string; otp: string; lang: Lang; role: string; display_name: string; scenarios: string[] };

const field = "w-full rounded-control border border-b-line bg-b-surface px-3 py-2.5 text-base text-b-ink focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-b-cobalt";
const primary = "w-full rounded-full bg-b-leaf py-3 text-base font-bold text-b-surface transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-cobalt disabled:opacity-60";

export function LoginForm({ next, embed, prefillUser, shortTtl = false, auto = false }:
  { next: string; embed: boolean; prefillUser?: string; shortTtl?: boolean; auto?: boolean }) {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("es");
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [ticket, setTicket] = useState<string | null>(null);
  const [otp, setOtp] = useState("");
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const d = t(lang);

  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  useEffect(() => {
    fetch("/api/auth/demo-users").then(async (r) => (r.ok ? ((await r.json()).data as DemoUser[]) : [])).then((list) => {
      setUsers(list);
      const pick = list.find((u) => u.username === prefillUser) ?? list.find((u) => u.lang === "es") ?? list[0];
      if (pick) { setLang(pick.lang); setUsername(pick.username); setPassword(pick.demo_password); setOtp(pick.otp); }
    }).catch(() => setUsers([]));
  }, [prefillUser]);

  const visible = useMemo(() => users.filter((u) => u.lang === lang), [users, lang]);
  const pickUser = (u: DemoUser) => { setUsername(u.username); setPassword(u.demo_password); setOtp(u.otp); };
  const chooseLang = (l: Lang) => {
    setLang(l);
    const first = users.find((u) => u.lang === l);
    if (first) pickUser(first);
    else { setUsername(""); setPassword(""); setOtp(""); }
  };
  const chooseUser = (name: string) => {
    const u = users.find((x) => x.username === name);
    if (u) pickUser(u); else setUsername(name);
  };

  const onLangKey = (e: React.KeyboardEvent) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    const l = lang === "es" ? "pt" : "es";
    chooseLang(l);
    (e.currentTarget.parentElement?.querySelector(`[aria-checked="false"]`) as HTMLElement | null)?.focus();
  };
  async function post(url: string, body: object) {
    return fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  }
  async function requestTicket(): Promise<string | null> {
    const r = await post("/api/auth/login", { username, password });
    return r.ok ? ((await r.json()).data.login_ticket as string) : null;
  }
  async function verifyOtp(tk: string) {
    const r = await post("/api/auth/otp", { login_ticket: tk, otp, short_ttl: shortTtl });
    if (!r.ok) return setError(true);
    notifyParent({ type: "demo:auth", step: "otp_verified" });
    notifyParent({ type: "demo:auth", step: "token_issued" });
    router.replace(embed ? `${next}${next.includes("?") ? "&" : "?"}embed=1` : next);
  }
  async function run(step: () => Promise<void>) {
    setBusy(true); setError(false);
    try { await step(); } catch { setError(true); } finally { setBusy(false); }
  }
  const submitCredentials = () => run(async () => {
    const tk = await requestTicket();
    if (tk) setTicket(tk); else setError(true);
  });
  const submitOtp = () => run(async () => { if (ticket) await verifyOtp(ticket); });

  useEffect(() => {  // /demo scenarios: sign in without clicks (demo users only)
    if (!auto || !username || !password || ticket) return;
    void (async () => {
      try {
        const tk = await requestTicket();
        if (!tk) return setError(true);
        setTicket(tk);
        await verifyOtp(tk);
      } catch { setError(true); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, username, password]);

  return (
    <main className="font-customer min-h-dvh bg-b-fog text-b-ink flex justify-center">
      <div className="flex min-h-dvh w-full max-w-md flex-col bg-b-surface sm:my-6 sm:min-h-0 sm:overflow-hidden sm:rounded-card sm:border sm:border-b-line">
        <header className="relative overflow-hidden rounded-b-card bg-b-cobalt px-6 pb-14 pt-8 text-b-surface">
          <span aria-hidden className="absolute -right-10 -top-10 size-40 rounded-full bg-b-sun" />
          <span aria-hidden className="absolute -bottom-12 right-16 size-32 rounded-full bg-b-leaf" />
          <p className="relative text-lg font-extrabold tracking-tight">{d.bank}</p>
          <h1 className="relative mt-6 max-w-[16ch] text-3xl font-extrabold leading-tight">{d.loginTitle}</h1>
        </header>

        <form className="relative z-10 -mt-8 mx-4 flex flex-col gap-4 rounded-card border border-b-line bg-b-surface p-5"
          onSubmit={(e) => { e.preventDefault(); void (ticket ? submitOtp() : submitCredentials()); }}>
          <div role="radiogroup" aria-label={d.language} className="flex rounded-full bg-b-mist p-1">
            {(["es", "pt"] as const).map((l) => (
              <button key={l} type="button" role="radio" aria-checked={lang === l} tabIndex={lang === l ? 0 : -1}
                onClick={() => chooseLang(l)} onKeyDown={onLangKey}
                className={`min-h-11 flex-1 rounded-full text-sm font-semibold focus-visible:outline-2 focus-visible:outline-b-cobalt ${lang === l ? "bg-b-cobalt text-b-surface" : "text-b-muted"}`}>
                {l === "es" ? "Español" : "Português"}
              </button>
            ))}
          </div>

          {!ticket ? (
            <>
              <label className="flex flex-col gap-1.5 text-sm font-semibold">{d.identity}
                {visible.length > 0 ? (
                  <select className={field} value={username} onChange={(e) => chooseUser(e.target.value)}>
                    {visible.map((u) => (
                      <option key={u.username} value={u.username}>{u.display_name ? `${u.display_name} · ${u.username}` : u.username}</option>
                    ))}
                  </select>
                ) : (
                  <input className={field} value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
                )}
              </label>
              <label className="flex flex-col gap-1.5 text-sm font-semibold">{d.password}
                <input type="password" className={field} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
              </label>
              <button disabled={busy || !username || !password} className={primary}>{d.continue}</button>
            </>
          ) : (
            <>
              <p className="rounded-control bg-b-sun-tint px-3 py-2 text-sm text-b-ink">{d.codeSent}</p>
              <label className="flex flex-col gap-1.5 text-sm font-semibold">{d.code}
                <input inputMode="numeric" autoComplete="one-time-code" value={otp} onChange={(e) => setOtp(e.target.value)}
                  className="w-full rounded-control bg-b-mist px-3 py-3 text-center text-2xl font-extrabold tracking-[0.4em] text-b-ink focus-visible:outline-2 focus-visible:outline-b-cobalt" />
              </label>
              <button disabled={busy || !otp} className={primary}>{d.enter}</button>
            </>
          )}
          {error && <p role="alert" className="rounded-control bg-b-sun-tint px-3 py-2 text-sm text-b-ink">{d.loginFailed}</p>}
        </form>

        <p className="mt-auto px-6 py-6 text-center text-xs text-b-muted">{d.demoFooter}</p>
      </div>
    </main>
  );
}
