"""JSON-only calls: the model gets no tools, only text in and schema-valid JSON out."""
import json
import os
import time
from dataclasses import dataclass
from types import SimpleNamespace

import openai

from bankagent.llm.config import RoleConfig


class LLMError(Exception):
    pass


class LLMRefusal(LLMError):
    pass


@dataclass(frozen=True)
class LLMCall:
    data: dict
    model: str
    prompt_version: str
    usage: dict
    latency_ms: int


def _bedrock_session():
    """With BEDROCK_ROLE_ARN set every call runs as that role (another account); unset, this account's credentials."""
    import boto3

    role = os.environ.get("BEDROCK_ROLE_ARN")
    if not role:
        return boto3.Session(profile_name=os.environ.get("AWS_PROFILE"))
    kw = {"ExternalId": os.environ["BEDROCK_EXTERNAL_ID"]} if os.environ.get("BEDROCK_EXTERNAL_ID") else {}
    # Assumed creds last 1 h; RefreshingClient re-mints (and so re-assumes) every 30 min.
    c = boto3.client("sts").assume_role(RoleArn=role, RoleSessionName="lb-demo-agent", **kw)["Credentials"]
    return boto3.Session(aws_access_key_id=c["AccessKeyId"], aws_secret_access_key=c["SecretAccessKey"],
                         aws_session_token=c["SessionToken"])


def _generate_bedrock_token(region: str = "us-east-1", session=None) -> str:
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    
    credentials = (session or _bedrock_session()).get_credentials()
    frozen = credentials.get_frozen_credentials()
    
    service = "bedrock-mantle"
    host = f"bedrock-mantle.{region}.api.aws"
    url = f"https://{host}/v1/chat/completions"
    
    request = AWSRequest(method="POST", url=url, headers={"host": host})
    
    auth = SigV4Auth(frozen, service, region)
    auth.add_auth(request)
    
    auth_header = request.headers.get("Authorization", "")
    return auth_header


class RefreshingClient:
    """Mantle tokens expire with the session credentials: re-mint before max_age_s and on rejection."""

    def __init__(self, factory, max_age_s: float = 1800, clock=time.monotonic):
        self._factory, self._max_age, self._clock = factory, max_age_s, clock
        self.refresh()

    def refresh(self) -> None:
        self._client, self._born = self._factory(), self._clock()

    @property
    def chat(self):
        if self._clock() - self._born > self._max_age:
            self.refresh()
        return self._client.chat


def make_bedrock_client(region: str = "us-east-1"):
    return RefreshingClient(lambda: _mantle_client(region))


def _mantle_client(region: str):
    base_url = os.environ.get("OPENAI_BASE_URL", f"https://bedrock-mantle.{region}.api.aws/v1")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        session = _bedrock_session()
        try:
            from aws_bedrock_token_generator import provide_token
            api_key = provide_token(region=region, aws_credentials_provider=SimpleNamespace(load=session.get_credentials))
        except ImportError:
            api_key = _generate_bedrock_token(region, session)
    
    return openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=30.0,   # ceiling only: every call passes its role's timeout (models.yaml) or the turn budget's remainder
        max_retries=0,  # retries are explicit in the graph (extract → original text, compose → one regeneration)
    )


def call_json(client, cfg: RoleConfig, system: str, user: str, schema: dict) -> LLMCall:
    start = time.monotonic()
    request = dict(
        model=cfg.model,
        max_tokens=cfg.max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_schema", "json_schema": {"name": "response", "schema": schema}},
    )
    if cfg.effort:  # reasoning models only (gpt-oss): left unset they reason at default effort and hit max_tokens
        request["reasoning_effort"] = cfg.effort
    try:
        try:
            resp = client.chat.completions.create(**request, timeout=cfg.timeout_s)
        except (openai.AuthenticationError, openai.PermissionDeniedError):
            if not hasattr(client, "refresh"):
                raise
            client.refresh()  # stale Mantle token: mint a fresh one and retry once
            resp = client.chat.completions.create(**request, timeout=cfg.timeout_s)
    except openai.APIError as e:
        raise LLMError(f"{type(e).__name__}: {e}") from e
    except openai.APIConnectionError as e:
        raise LLMError(f"Connection error: {e}") from e
    except openai.RateLimitError as e:
        raise LLMError(f"Rate limit: {e}") from e
    except openai.AuthenticationError as e:
        raise LLMError(f"Auth error: {e}") from e

    if not resp.choices:
        raise LLMError(f"No choices in response. Raw response: {resp}")

    if resp.choices[0].finish_reason == "length":
        raise LLMError("truncated output")

    text = resp.choices[0].message.content
    if not text:
        raise LLMError(f"Empty message content. Finish reason: {resp.choices[0].finish_reason}")

    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    text = text.strip()

    def _unique(pairs):
        # A duplicated key means the model rewrote a value mid-object: malformed output is an error, never a reply.
        obj = {}
        for k, v in pairs:
            if k in obj:
                raise ValueError(f"duplicate key: {k!r}")
            obj[k] = v
        return obj

    def _load(candidate):
        return json.loads(candidate, object_pairs_hook=_unique)

    first_brace = text.find("{")

    for start_idx in range(len(text)):
        if text[start_idx] != '{':
            continue
        
        brace_count = 0
        for end_idx in range(start_idx, len(text)):
            if text[end_idx] == '{':
                brace_count += 1
            elif text[end_idx] == '}':
                brace_count -= 1
                if brace_count == 0:
                    candidate = text[start_idx:end_idx + 1]
                    try:
                        data = _load(candidate)
                    except (TypeError, ValueError):
                        continue
                    if start_idx != first_brace and set(text[first_brace:start_idx]) - set("{ \t\r\n"):
                        # An unparsed object then a parsed fragment is a decoder restart: never reply from it.
                        raise LLMError(f"ambiguous JSON output: {text[:200]}")
                    text = candidate
                    break
        else:
            continue
        break
    else:
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx >= 0 and end_idx > start_idx:
            text = text[start_idx:end_idx + 1]

    try:
        data = _load(text)
    except (TypeError, ValueError) as e:
        raise LLMError(f"invalid JSON output: {text[:200]}") from e

    usage = {
        "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }
    return LLMCall(data, cfg.model, cfg.prompt_version, usage, int((time.monotonic() - start) * 1000))


def warm_up(client, models: dict) -> None:
    """Warm each live role's model at start so the slow first call doesn't eat a turn. Never raises."""
    import logging
    log = logging.getLogger(__name__)
    for role in ("extract", "compose"):
        cfg = models[role]
        try:
            client.chat.completions.create(model=cfg.model, max_tokens=1, timeout=30,
                                           messages=[{"role": "user", "content": "ok"}])
        except Exception as e:  # noqa: BLE001 - warm-up must never stop the runtime
            log.warning("model warm-up failed", extra={"role": role, "error": type(e).__name__})
