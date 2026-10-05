"""OpenAI on Bedrock Mantle, JSON-only calls. OpenAI has no tools here: input text in, schema-valid JSON out."""
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
    """Credentials that sign Bedrock calls. With BEDROCK_ROLE_ARN set, every call runs as that role (in another
    account, so its model access, quotas and bill apply); unset, this account's own credentials."""
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
    """Generate a SigV4-signed token for Bedrock Mantle API using AWS credentials."""
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    
    credentials = (session or _bedrock_session()).get_credentials()
    frozen = credentials.get_frozen_credentials()
    
    # Create the request to sign
    service = "bedrock-mantle"
    host = f"bedrock-mantle.{region}.api.aws"
    url = f"https://{host}/v1/chat/completions"
    
    request = AWSRequest(method="POST", url=url, headers={"host": host})
    
    # Sign the request
    auth = SigV4Auth(frozen, service, region)
    auth.add_auth(request)
    
    # Extract the Authorization header as the token
    auth_header = request.headers.get("Authorization", "")
    return auth_header


class RefreshingClient:
    """Mantle bearer tokens are minted from the runtime role's session credentials, which expire (about 1 h), so a
    token minted once per container goes stale mid-demo. Re-mint before `max_age_s`, and on demand when the endpoint
    rejects the token (`call_json` calls `refresh()` once)."""

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
    """An OpenAI client for the Bedrock Mantle endpoint whose token is re-minted before it expires."""
    return RefreshingClient(lambda: _mantle_client(region))


def _mantle_client(region: str):
    """Create an OpenAI client configured for Bedrock Mantle endpoint."""
    base_url = os.environ.get("OPENAI_BASE_URL", f"https://bedrock-mantle.{region}.api.aws/v1")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        session = _bedrock_session()
        # Try to import the token generator, fall back to SigV4 signing
        try:
            from aws_bedrock_token_generator import provide_token
            api_key = provide_token(region=region, aws_credentials_provider=SimpleNamespace(load=session.get_credentials))
        except ImportError:
            api_key = _generate_bedrock_token(region, session)
    
    return openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=30.0,
        max_retries=1,
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
    try:
        try:
            resp = client.chat.completions.create(**request)
        except (openai.AuthenticationError, openai.PermissionDeniedError):
            if not hasattr(client, "refresh"):
                raise
            client.refresh()  # stale Mantle token: mint a fresh one and retry once
            resp = client.chat.completions.create(**request)
    except openai.APIError as e:
        raise LLMError(f"{type(e).__name__}: {e}") from e
    except openai.APIConnectionError as e:
        raise LLMError(f"Connection error: {e}") from e
    except openai.RateLimitError as e:
        raise LLMError(f"Rate limit: {e}") from e
    except openai.AuthenticationError as e:
        raise LLMError(f"Auth error: {e}") from e

    # Check if choices exist
    if not resp.choices:
        raise LLMError(f"No choices in response. Raw response: {resp}")

    if resp.choices[0].finish_reason == "length":
        raise LLMError("truncated output")

    text = resp.choices[0].message.content
    if not text:
        raise LLMError(f"Empty message content. Finish reason: {resp.choices[0].finish_reason}")

    # Strip markdown code block wrappers if present (common with OSS models)
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]  # Remove ```json prefix
    elif text.startswith("```"):
        text = text[3:]  # Remove ``` prefix
    if text.endswith("```"):
        text = text[:-3]  # Remove ``` suffix
    text = text.strip()

    # Extract JSON object using brace counting to find complete JSON
    # OSS models often add text before/after, or have nested structures
    text = text.strip()

    def _unique(pairs):
        # A duplicated key means the model split or rewrote a value mid-object; the silent last-wins
        # drop produced replies missing their first clause. Malformed output is an error, never a reply.
        obj = {}
        for k, v in pairs:
            if k in obj:
                raise ValueError(f"duplicate key: {k!r}")
            obj[k] = v
        return obj

    def _load(candidate):
        return json.loads(candidate, object_pairs_hook=_unique)

    first_brace = text.find("{")

    # Try to find complete JSON by counting braces
    for start_idx in range(len(text)):
        if text[start_idx] != '{':
            continue
        
        # Count braces to find matching end
        brace_count = 0
        for end_idx in range(start_idx, len(text)):
            if text[end_idx] == '{':
                brace_count += 1
            elif text[end_idx] == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found complete JSON object
                    candidate = text[start_idx:end_idx + 1]
                    try:
                        data = _load(candidate)
                    except (TypeError, ValueError):
                        # Not valid JSON, continue searching
                        continue
                    if start_idx != first_brace:
                        # The output started an object that never parsed and a later fragment did:
                        # a decoder restart. Never reply from a salvaged fragment.
                        raise LLMError(f"ambiguous JSON output: {text[:200]}")
                    # Successfully parsed!
                    text = candidate
                    break
        else:
            # No matching } found for this {, try next
            continue
        break  # Successfully parsed, exit outer loop
    else:
        # No valid JSON found, try original extraction
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
