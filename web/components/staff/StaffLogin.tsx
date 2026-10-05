"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Staff = { username: string; demo_password: string; display_name: string };
const field = "border border-c-line rounded-control px-3 py-2.5 bg-c-panel text-c-ink font-normal focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-c-signal";

export function StaffLogin({ next }: { next: string }) {
  const router = useRouter();
  const [staff, setStaff] = useState<Staff[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    fetch("/api/auth/demo-users?role=agent").then(async (r) => (r.ok ? ((await r.json()).data as Staff[]) : [])).then((list) => {
      setStaff(list);
      if (list[0]) { setUsername(list[0].username); setPassword(list[0].demo_password); }
    }).catch(() => setStaff([]));
  }, []);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(false);
    try {
      const r = await fetch("/api/auth/staff-login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ username, password }) });
      if (!r.ok) return setError(true);
      router.replace(next);
    } catch { setError(true); } finally { setBusy(false); }
  }
  return (
    <main className="font-staff min-h-dvh bg-c-canvas text-c-ink flex flex-col">
      <div className="bg-c-ink text-c-canvas px-6 py-3 text-sm font-bold">LATAM Bank · Agent console</div>
      <div className="flex-1 flex items-center justify-center p-4">
        <form onSubmit={submit} className="bg-c-panel rounded-panel ring-1 ring-c-line p-6 w-full max-w-sm flex flex-col gap-4">
          <div>
            <h1 className="text-lg font-bold">Staff sign-in</h1>
            <p className="text-sm text-c-muted mt-0.5">Work the handoff queue and take over chats.</p>
          </div>
          <label className="flex flex-col gap-1 text-sm font-semibold">Staff identity
            {staff.length ? (
              <select value={username} className={field}
                onChange={(e) => { const s = staff.find((x) => x.username === e.target.value); setUsername(e.target.value); setPassword(s?.demo_password ?? ""); }}>
                {staff.map((s) => <option key={s.username} value={s.username}>{s.display_name ? `${s.display_name} · ${s.username}` : s.username}</option>)}
              </select>
            ) : <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" className={field} />}
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className={field} />
          </label>
          <button disabled={busy} className="rounded-control bg-c-signal text-c-panel py-2.5 font-bold hover:opacity-90 disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-c-signal">Sign in</button>
          {error && <p role="alert" className="text-sm text-c-alert">Those staff credentials didn&apos;t work. Check the identity and password.</p>}
          <p className="text-xs text-c-muted">Demo · labeled test identities · synthetic data</p>
        </form>
      </div>
    </main>
  );
}
