"""AgentCore Runtime entrypoint (spec §3.2 step 1): POST /invocations, GET /ping on :8080.
AgentCore's CUSTOM_JWT authorizer checks the token first and forwards Authorization (requestHeaderAllowlist);
this code re-verifies it anyway. customer_id comes only from the token, never from the payload."""
import logging

from bedrock_agentcore import BedrockAgentCoreApp, RequestContext

from bankagent.auth.tokens import AuthError, verify_token
from bankagent.llm.templates import auth_message, fallback_reply
from bankagent.settings import Settings

MAX_MESSAGE_CHARS = 2000
log = logging.getLogger(__name__)
app = BedrockAgentCoreApp()
_runtime = None


def _error(text: str, lang: str, error: str) -> dict:
    return {"reply_text": text, "language": lang, "awaiting": "none", "options": [], "refs": [], "data_as_of": None,
            "error": error}


def _bearer(headers: dict) -> str | None:
    for name, value in (headers or {}).items():
        if name.lower() == "authorization" and isinstance(value, str) and value.lower().startswith("bearer "):
            return value[7:].strip()
    return None


def handle(payload: dict, headers: dict, rt) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    lang = payload.get("lang") if payload.get("lang") in ("es", "pt") else "es"
    token = _bearer(headers) or payload.get("session_token")
    if not isinstance(token, str) or not token:
        return _error(auth_message("auth_required", lang), lang, "auth_required")
    try:
        jwks = rt.jwks.get()
    except Exception:
        log.exception("identity service unavailable")
        return _error(fallback_reply({"kind": "error"}, [], lang), lang, "identity_unavailable")
    try:
        ctx = verify_token(token, jwks, rt.settings.issuer, rt.settings.audience)
    except AuthError as e:
        kind = "session_expired" if str(e) == "expired" else "auth_required"
        return _error(auth_message(kind, lang), lang, kind)
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip() or len(message) > MAX_MESSAGE_CHARS:
        return _error(auth_message("invalid_message", ctx.lang), ctx.lang, "invalid_message")
    return rt.service.handle_turn(ctx, message.strip())


def runtime():
    global _runtime
    if _runtime is None:
        from bankagent.runtime import build_runtime
        _runtime = build_runtime(Settings.from_env())
    return _runtime


@app.entrypoint
def invoke(payload, context: RequestContext):
    return handle(payload, context.request_headers or {}, runtime())


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
