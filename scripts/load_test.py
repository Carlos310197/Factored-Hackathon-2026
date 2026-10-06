"""Small concurrent load test against the live app (stdlib only).

N customers sign in at once (each sign-in warms its own agent session), wait like a person would, then send the same
short conversation. Prints one line per turn and a summary (p50/p95, errors). Costs real Bedrock and Jev calls: run
only with the owner's approval.

    python3 scripts/load_test.py https://d21y0qq5d8ixnr.cloudfront.net --users 10
"""
import argparse
import http.cookiejar
import json
import statistics
import threading
import time
import urllib.error
import urllib.request

MESSAGES = ["¿Cuál es el saldo de mis cuentas?", "¿Tengo algún pago rechazado?", "Gracias"]


def session(base: str, user: str, think_s: float, out: list, lock: threading.Lock) -> None:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def post(path, body, timeout=40):
        req = urllib.request.Request(base + path, json.dumps(body).encode(), {"content-type": "application/json"})
        start = time.monotonic()
        try:
            with opener.open(req, timeout=timeout) as r:
                return r.status, json.loads(r.read()), time.monotonic() - start
        except urllib.error.HTTPError as e:
            return e.code, {}, time.monotonic() - start
        except Exception as e:  # timeouts, resets
            return 0, {"error": str(e)}, time.monotonic() - start

    _, login, _ = post("/api/auth/login", {"username": user, "password": f"demo-{user[4:]}"})
    ticket = (login.get("data") or {}).get("login_ticket", "")
    status, _, _ = post("/api/auth/otp", {"login_ticket": ticket, "otp": "123456"})
    if status != 200:
        with lock:
            out.append({"user": user, "turn": 0, "status": status, "s": 0.0, "turn_id": None, "error": "login"})
        return
    for i, text in enumerate(MESSAGES, 1):
        time.sleep(think_s)
        status, body, secs = post("/api/chat", {"message": text,
                                                "client_message_id": f"load-{user}-{i}-{int(time.time())}"})
        err = body.get("error")
        row = {"user": user, "turn": i, "status": status, "s": round(secs, 2),
               "turn_id": (body.get("data") or {}).get("turn_id"),
               "error": err.get("code") if isinstance(err, dict) else err}
        with lock:
            out.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--users", type=int, default=10)
    ap.add_argument("--first", type=int, default=9, help="first demo user number (demoNN)")
    ap.add_argument("--think", type=float, default=8.0, help="seconds between messages")
    a = ap.parse_args()
    out, lock = [], threading.Lock()
    users = [f"demo{n:02d}" for n in range(a.first, a.first + a.users)]
    started = time.time()
    threads = [threading.Thread(target=session, args=(a.base.rstrip("/"), u, a.think, out, lock)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    turns = [r for r in out if r["turn"] > 0]
    ok = sorted(r["s"] for r in turns if r["status"] == 200)
    p95 = statistics.quantiles(ok, n=20)[18] if len(ok) >= 2 else None
    print(json.dumps({"users": len(users), "turns": len(turns), "ok": len(ok),
                      "errors": [r for r in out if r["status"] != 200],
                      "p50_s": round(statistics.median(ok), 2) if ok else None,
                      "p95_s": round(p95, 2) if p95 else None, "max_s": max(ok) if ok else None,
                      "wall_s": round(time.time() - started, 1),
                      "started_utc": time.strftime("%H:%M:%SZ", time.gmtime(started))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
