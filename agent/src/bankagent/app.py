"""AgentCore Runtime entrypoint (spec §3.2 step 1): POST /invocations, GET /ping on :8080.
AgentCore's CUSTOM_JWT authorizer checks the token first and forwards Authorization (requestHeaderAllowlist);
this code re-verifies it anyway. customer_id comes only from the token, never from the payload."""
import logging
import re
import threading
import time
from datetime import date

from bedrock_agentcore import BedrockAgentCoreApp, RequestContext

from bankagent.auth.tokens import AuthError, verify_token
from bankagent.ids import new_id
from bankagent.llm.templates import auth_message, fallback_reply
from bankagent.settings import load_settings

MAX_MESSAGE_CHARS = 2000
MESSAGE_ID_HEADER = "x-amzn-bedrock-agentcore-runtime-custom-message-id"  # the prefix AgentCore passes through
MESSAGE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
META_KEYS = ("language", "awaiting", "options", "refs", "summary", "data_as_of")
log = logging.getLogger(__name__)
# One plain line per turn on stderr, parsed by a CloudWatch metric filter into TurnDurationMs (dashboard p50/p95).
metrics = logging.getLogger("bankagent.metrics")
if not metrics.handlers:
    metrics.addHandler(logging.StreamHandler())
    metrics.setLevel(logging.INFO)
    metrics.propagate = False
app = BedrockAgentCoreApp()
_runtime = None
_runtime_lock = threading.Lock()


def _error(text: str, lang: str, error: str) -> dict:
    return {"reply_text": text, "language": lang, "awaiting": "none", "options": [], "refs": [], "data_as_of": None,
            "error": error}


def _bearer(headers: dict) -> str | None:
    for name, value in (headers or {}).items():
        if name.lower() == "authorization" and isinstance(value, str) and value.lower().startswith("bearer "):
            return value[7:].strip()
    return None


def _header(headers: dict, name: str) -> str | None:
    for key, value in (headers or {}).items():
        if key.lower() == name and isinstance(value, str):
            return value
    return None


def _message_id(payload: dict, headers: dict) -> str:
    raw = _header(headers, MESSAGE_ID_HEADER) or payload.get("client_message_id")
    return raw if isinstance(raw, str) and MESSAGE_ID_RE.match(raw) else new_id("MSG")


def warm(token: str, rt) -> dict:
    """Login-time warm-up of this runtime session's microVM (the BFF calls it after the OTP): runtime built, models
    warming, JWKS cached, and one read of the caller's own accounts so DuckDB and the serving set are hot.
    No turn, no session row, no message: it only reads, and a failure is just a cold first turn."""
    try:
        ctx = verify_token(token, rt.jwks.get(), rt.settings.issuer, rt.settings.audience)
        sid = ctx.session_id
        read = rt.service.deps.read
        pointer = read.serving.pointer()
        read.get_accounts(ctx, pointer.run_id, date.fromisoformat(str(pointer.max_process_date)[:10]))
        return {"warm": True, "sid": sid}
    except Exception:
        log.warning("warm-up failed", exc_info=True)
        return {"warm": False}


def handle(payload: dict, headers: dict, rt) -> dict:
    """Every request, turn or not, leaves one `request <outcome> <session> <message_id>` line (metric `Requests`)."""
    note = {"outcome": "turn", "sid": "-", "mid": "-"}
    try:
        return _handle(payload, headers, rt, note)
    finally:
        metrics.info("request %s %s %s", note["outcome"], note["sid"], note["mid"])


def _handle(payload: dict, headers: dict, rt, note: dict) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    lang = payload.get("lang") if payload.get("lang") in ("es", "pt") else "es"
    token = _bearer(headers)  # header only: no token in the payload
    if not isinstance(token, str) or not token:
        note["outcome"] = "auth_required"
        return _error(auth_message("auth_required", lang), lang, "auth_required")
    if payload.get("warmup") is True:
        result = warm(token, rt)
        note["outcome"], note["sid"] = ("warmup_ok" if result["warm"] else "warmup_failed"), result.get("sid", "-")
        return {"warm": result["warm"]}
    try:
        jwks = rt.jwks.get()
    except Exception:
        log.exception("identity service unavailable")
        note["outcome"] = "identity_unavailable"
        return _error(fallback_reply({"kind": "error"}, [], lang), lang, "identity_unavailable")
    try:
        ctx = verify_token(token, jwks, rt.settings.issuer, rt.settings.audience)
    except AuthError as e:
        kind = "session_expired" if str(e) == "expired" else "auth_required"
        note["outcome"] = kind
        return _error(auth_message(kind, lang), lang, kind)
    note["sid"] = ctx.session_id
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip() or len(message) > MAX_MESSAGE_CHARS:
        note["outcome"] = "invalid_message"
        return _error(auth_message("invalid_message", ctx.lang), ctx.lang, "invalid_message")
    text, sid, store = message.strip(), ctx.session_id, rt.service.deps.store
    store.sessions.ensure(sid, ctx.customer_id, ctx.lang)
    message_id = _message_id(payload, headers)
    note["mid"] = message_id
    prior = store.messages.claim(sid, message_id)
    if prior is not None:
        note["outcome"] = "duplicate"  # a retry or double send of the same message: never run the turn twice
        return prior.get("reply") or {**_error("", ctx.lang, "duplicate_in_progress"), "turn_id": None}
    if store.sessions.control(sid) != "agent":  # a human holds the conversation
        note["outcome"] = "human_control"
        store.messages.append(sid, "customer", text, message_id=message_id)
        reply = {"reply_text": "", "language": ctx.lang, "awaiting": "human", "options": [], "refs": [],
                 "data_as_of": None, "turn_id": None}
        store.messages.store_reply(sid, message_id, reply)
        return reply
    turn_id, start = new_id("TRN"), time.monotonic()
    try:
        store.messages.append(sid, "customer", text, message_id=message_id, turn_id=turn_id)
        reply = rt.service.handle_turn(ctx, text, turn_id=turn_id)
        store.messages.append(sid, "assistant", reply.get("reply_text", ""), turn_id=turn_id,
                              meta={k: reply.get(k) for k in META_KEYS if reply.get(k) is not None})
    except Exception:  # never leave the marker `running`: a retry would get duplicate_in_progress until the TTL
        log.exception("turn failed session=%s turn=%s", sid, turn_id)
        note["outcome"] = "turn_failed"
        reply = {**_error(fallback_reply({"kind": "error"}, [], ctx.lang), ctx.lang, "turn_failed"), "turn_id": turn_id}
    duration_ms = int((time.monotonic() - start) * 1000)
    metrics.info("turn_end %d", duration_ms)
    store.log.append(sid, turn_id, "turn", "turn_end",
                     {"duration_ms": duration_ms, "awaiting": reply.get("awaiting", "none"),
                      "language": reply.get("language", ctx.lang)})
    store.messages.store_reply(sid, message_id, reply)
    return reply


def runtime():
    global _runtime
    with _runtime_lock:  # the login warm-up and the first message can arrive together: build once
        if _runtime is None:
            from bankagent.runtime import build_runtime
            _runtime = build_runtime(load_settings())
    return _runtime


@app.entrypoint
def invoke(payload, context: RequestContext):
    return handle(payload, context.request_headers or {}, runtime())


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
