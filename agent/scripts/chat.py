import argparse

import httpx


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--otp", default="123456")
    ap.add_argument("--idp", default="http://localhost:8081")
    ap.add_argument("--agent", default="http://localhost:8080")
    a = ap.parse_args()
    ticket = httpx.post(f"{a.idp}/auth/login", json={"username": a.user, "password": a.password}).raise_for_status()
    token = httpx.post(f"{a.idp}/auth/otp", json={"login_ticket": ticket.json()["login_ticket"], "otp": a.otp})
    token.raise_for_status()
    bearer = {"Authorization": f"Bearer {token.json()['access_token']}"}
    print(f"logged in as {a.user} ({token.json()['lang']}); /quit to exit")
    while True:
        try:
            msg = input("you> ")
        except EOFError:
            break
        if msg.strip() in ("/quit", "/exit"):
            break
        r = httpx.post(f"{a.agent}/invocations", json={"message": msg}, headers=bearer, timeout=60).json()
        print(f"agent> {r['reply_text']}")
        for i, option in enumerate(r.get("options") or [], start=1):
            print(f"   {i}. {option}")
        if r.get("refs"):
            print(f"   refs: {', '.join(r['refs'])}   data as of {r.get('data_as_of')}")


if __name__ == "__main__":
    main()
