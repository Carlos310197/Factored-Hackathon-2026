"""Claude on Bedrock, JSON-only calls. Claude has no tools here: input text in, schema-valid JSON out."""
import json
import time
from dataclasses import dataclass

import anthropic

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
    from anthropic import AnthropicBedrockMantle
    return AnthropicBedrockMantle(aws_region=region, max_retries=1)  # one retry on 408/429/5xx/connection errors


def call_json(client, cfg: RoleConfig, system: str, user: str, schema: dict) -> LLMCall:
    output_config = {"format": {"type": "json_schema", "schema": schema}}
    if cfg.effort:
        output_config["effort"] = cfg.effort
    start = time.monotonic()
    try:
        resp = client.messages.create(
            model=cfg.model, max_tokens=cfg.max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}], output_config=output_config, timeout=cfg.timeout_s)
    except anthropic.APIError as e:
        raise LLMError(f"{type(e).__name__}: {e}") from e
    if resp.stop_reason == "refusal":
        raise LLMRefusal(cfg.model)
    if resp.stop_reason == "max_tokens":
        raise LLMError("truncated output")
    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), None)
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as e:
        raise LLMError("invalid JSON output") from e
    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    return LLMCall(data, cfg.model, cfg.prompt_version, usage, int((time.monotonic() - start) * 1000))
