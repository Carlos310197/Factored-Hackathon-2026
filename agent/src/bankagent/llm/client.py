"""OpenAI on Bedrock Mantle, JSON-only calls. OpenAI has no tools here: input text in, schema-valid JSON out."""
import json
import os
import time
from dataclasses import dataclass

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


def _generate_bedrock_token(region: str = "us-east-1") -> str:
    """Generate a SigV4-signed token for Bedrock Mantle API using AWS credentials."""
    import boto3
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    
    session = boto3.Session(profile_name=os.environ.get("AWS_PROFILE"))
    credentials = session.get_credentials()
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


def make_bedrock_client(region: str = "us-east-1"):
    """Create an OpenAI client configured for Bedrock Mantle endpoint."""
    base_url = os.environ.get("OPENAI_BASE_URL", f"https://bedrock-mantle.{region}.api.aws/v1")
    
    # Try to import the token generator, fall back to SigV4 signing
    try:
        from aws_bedrock_token_generator import provide_token
        api_key = os.environ.get("OPENAI_API_KEY") or provide_token(region=region)
    except ImportError:
        api_key = os.environ.get("OPENAI_API_KEY") or _generate_bedrock_token(region)
    
    return openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=30.0,
        max_retries=1,
    )


def call_json(client, cfg: RoleConfig, system: str, user: str, schema: dict) -> LLMCall:
    start = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=cfg.model,
            max_tokens=cfg.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_schema", "json_schema": {"name": "response", "schema": schema}},
        )
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
                        data = json.loads(candidate)
                        # Successfully parsed!
                        text = candidate
                        break
                    except (TypeError, ValueError):
                        # Not valid JSON, continue searching
                        continue
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
        data = json.loads(text)
    except (TypeError, ValueError) as e:
        raise LLMError(f"invalid JSON output: {text[:200]}") from e

    usage = {
        "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }
    return LLMCall(data, cfg.model, cfg.prompt_version, usage, int((time.monotonic() - start) * 1000))
