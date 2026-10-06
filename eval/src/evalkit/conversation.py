"""One simulated conversation against the agent's real entrypoint. Persona time is never counted."""
import secrets
import time
from dataclasses import dataclass

from bankagent.auth.tokens import generate_keypair, issue_token, jwks_from_public

from evalkit.persona import PersonaError, check_message

SCOPES = ["inquiry:read", "dispute:create"]
HANDOFF_STATUSES = ("open", "claimed", "in_takeover", "returned", "resolved")


@dataclass
class TokenIssuer:
    private_pem: str
    public_pem: str
    kid: str
    issuer: str
    audience: str

    @classmethod
    def generate(cls, issuer: str, audience: str, kid: str = "eval-1") -> "TokenIssuer":
        private_pem, public_pem = generate_keypair()
        return cls(private_pem, public_pem, kid, issuer, audience)

    @property
    def jwks(self) -> dict:
        return jwks_from_public(self.public_pem, self.kid)

    def issue(self, customer_id: str, session_id: str, lang: str, expired: bool = False) -> str:
        now = int(time.time()) - (3600 if expired else 0)
        return issue_token(self.private_pem, self.kid, self.issuer, self.audience, customer_id, session_id, SCOPES,
                           lang, ttl_s=900, now=now)


def snapshot(store, customer_id: str, session_id: str) -> dict:
    all_disputes = store.disputes.list_for_customer(customer_id)
    return {"disputes": [d for d in all_disputes if d.get("session_id") == session_id],
            "handoffs": [h for s in HANDOFF_STATUSES for h in store.handoffs.list_by_status(s)
                         if h.get("session_id") == session_id],
            "records": store.log.list(session_id),
            "customer_case_ids": sorted(d["dispute_id"] for d in all_disputes)}


def agent_text(reply: dict) -> str:
    text, opts = reply.get("reply_text") or "", reply.get("options") or []
    return text + ("\n" + " | ".join(map(str, opts)) if opts else "")


def run_conversation(card, rep: int, *, handle_fn, rt, store, persona, tokens: TokenIssuer, session_id=None,
                     clock=time.monotonic) -> dict:
    sid = session_id or f"EVAL-{card.goal_id}-r{rep}-{secrets.token_hex(8)}"
    rec = {"goal_id": card.goal_id, "rep": rep, "session_id": sid, "turns": [], "end_reason": None,
           "violations": [], "persona_usage": []}
    try:
        rec["before"] = snapshot(store, card.customer_id, sid)
        history = []
        for i in range(card.max_turns):
            pt = persona.next(card, history)
            rec["persona_usage"].append(pt.usage)
            if pt.done:
                rec["end_reason"] = "done"
                break
            violations = check_message(card, pt.text)
            if violations:
                rec |= {"end_reason": "persona_discarded", "violations": violations}
                break
            expired = card.fault == "expire_after_turn_1" and i >= 1
            token = tokens.issue(card.customer_id, sid, card.language, expired=expired)
            payload = {"message": pt.text, "client_message_id": f"{sid}-{i}", "lang": card.language}
            start = clock()
            reply = handle_fn(payload, {"Authorization": f"Bearer {token}"}, rt)
            latency = int(round((clock() - start) * 1000))
            rec["turns"].append({"i": i, "customer": pt.text, "reply": reply, "latency_ms": latency,
                                 "token_expired": expired})
            if reply.get("error") == "session_expired":
                rec["end_reason"] = "expired"
                break
            history.append({"customer": pt.text, "agent": agent_text(reply)})
        else:
            rec["end_reason"] = "max_turns"
        rec["after"] = snapshot(store, card.customer_id, sid)
    except PersonaError as e:
        rec |= {"end_reason": "harness_error", "error": f"persona: {e}"}
    except Exception as e:  # any agent or store failure the agent did not absorb is a harness error, never retried
        rec |= {"end_reason": "harness_error", "error": f"{type(e).__name__}: {e}"}
    return rec
