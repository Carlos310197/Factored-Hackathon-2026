"""OpenAI on Bedrock, JSON-only calls. OpenAI has no tools here: input text in, schema-valid JSON out."""
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


def make_bedrock_client(region: str):
    """Create an OpenAI client configured for Bedrock's OpenAI-compatible endpoint."""
    base_url = os.environ.get("OPENAI_BASE_URL", f"https://bedrock-runtime.{region}.amazonaws.com/models")
    api_key = os.environ.get("OPENAI_API_KEY", "bedrock")
    return openai.OpenAI(base_url=base_url, api_key=api_key, timeout=30.0, max_retries=1)


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

    if resp.choices[0].finish_reason == "length":
        raise LLMError("truncated output")

    text = resp.choices[0].message.content
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as e:
        raise LLMError("invalid JSON output") from e

    usage = {
        "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }
    return LLMCall(data, cfg.model, cfg.prompt_version, usage, int((time.monotonic() - start) * 1000))
