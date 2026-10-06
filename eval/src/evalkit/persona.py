"""Simulated customer: a non-Claude chat model served through OpenCode's OpenAI-compatible API."""
import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass

import httpx

DONE = "[DONE]"
MAX_CHARS = 600
ID_RE = re.compile(r"\b(?:TRX|CLI|PRD|DSP|HND)-[A-Z0-9]+\b")
OUT_OF_CHARACTER = ("as an ai", "language model", "modelo de lenguaje", "modelo de linguagem", "soy una ia",
                    "sou uma ia", "como ia,")
EN_WORDS = {"the", "and", "is", "my", "i", "you", "to", "of", "please", "charge", "card", "want", "what", "why",
            "was", "it", "this", "for", "with", "know"}
NATIVE_WORDS = {"el", "la", "de", "que", "mi", "por", "para", "una", "um", "uma", "não", "quiero", "quero", "cargo",
                "cobro", "tarjeta", "cartão", "cuenta", "conta", "gracias", "obrigado", "con", "com", "hola", "olá"}
LANG = {"es": "Latin American Spanish", "pt": "Brazilian Portuguese"}


class PersonaError(Exception):
    """The persona provider failed; the conversation is recorded as a harness error."""


@dataclass
class PersonaTurn:
    text: str | None
    done: bool
    usage: dict
    latency_ms: int


def check_message(card, text: str) -> list[str]:
    violations = []
    if len(text) > MAX_CHARS:
        violations.append("too_long")
    allowed = {str(v) for v in card.revealable_facts.values()}
    if any(i not in allowed for i in ID_RE.findall(text)):
        violations.append("id_leak")
    low = text.lower()
    if any(p in low for p in OUT_OF_CHARACTER):
        violations.append("out_of_character")
    words = re.findall(r"[a-záéíóúãõâêôçñü]+", low)
    en, native = sum(w in EN_WORDS for w in words), sum(w in NATIVE_WORDS for w in words)
    if card.message_style != "english" and en >= 3 and en > native:
        violations.append("wrong_language")
    if card.message_style == "english" and native > en:
        violations.append("wrong_language")
    return violations


def system_prompt(card) -> str:
    view = card.persona_view()
    other = LANG["pt" if card.language == "es" else "es"]
    style = {"native": f"Write every message in {LANG[card.language]}.",
             "mixed": f"Write in {LANG[card.language]}, but mix in a few words or one sentence of {other}.",
             "english": "Write every message in English."}[card.message_style]
    p = view["persona"]
    lines = ["You are role-playing a bank customer chatting with LATAM Bank's assistant. You are a person, never an AI.",
             style,
             f"Your private goal (do not paste it): {view['hidden_goal']}",
             f"Facts you may mention in your own words, only when useful: "
             f"{json.dumps(view['revealable_facts'], ensure_ascii=False)}",
             f"Personality: verbosity {p['verbosity']}, vagueness {p['vagueness']}, patience {p['patience']}."]
    if view["attack_script"]:
        lines.append("Follow these steps in order, one per message:")
        lines += [f"{k}. {step}" for k, step in enumerate(view["attack_script"], 1)]
    lines.append(f"Rules: write only your next chat message, under 400 characters. Never invent account numbers or ids. "
                 f"When your goal is achieved, or the assistant clearly cannot help and you have accepted that, reply "
                 f"with exactly {DONE}.")
    return "\n".join(lines)


class PersonaClient:
    def __init__(self, base_url: str, api_key: str, model: str, temperature: float | None, timeout_s: float = 30.0,
                 http: httpx.Client | None = None, api: str = "chat"):
        # api: "chat" (/chat/completions) or "responses" (/responses, which some OpenAI models need).
        # temperature None means the model's own default (some models reject the parameter).
        self.base_url, self.api_key, self.model, self.temperature = base_url.rstrip("/"), api_key, model, temperature
        self.api = api
        self.http = http or httpx.Client(timeout=timeout_s)

    @classmethod
    def from_config(cls, p: dict) -> "PersonaClient":
        return cls(p["base_url"], os.environ.get(p["api_key_env"], ""), p["model"], p.get("temperature"), p["timeout_s"],
                   api=p.get("api", "chat"))

    def next(self, card, history: list[dict]) -> PersonaTurn:
        messages = [{"role": "system", "content": system_prompt(card)}]
        if not history:
            messages.append({"role": "user", "content": "(The chat window just opened. Write your first message.)"})
        for h in history:
            messages += [{"role": "assistant", "content": h["customer"]}, {"role": "user", "content": h["agent"]}]
        if self.api == "responses":
            url, body = f"{self.base_url}/responses", {"model": self.model, "input": messages, "max_output_tokens": 1500}  # room for reasoning tokens
        else:
            url, body = f"{self.base_url}/chat/completions", {"model": self.model, "messages": messages, "max_tokens": 300}
        if self.temperature is not None:
            body["temperature"] = self.temperature
        for attempt in (0, 1):
            start = time.monotonic()
            try:
                r = self.http.post(url, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
            except httpx.TimeoutException as e:
                if attempt == 0:
                    continue
                raise PersonaError("timeout") from e
            if r.status_code >= 500 and attempt == 0:
                continue
            if r.status_code != 200:
                raise PersonaError(f"http {r.status_code}")
            data = r.json()
            text = self._text(data)
            usage, ms = data.get("usage") or {}, int((time.monotonic() - start) * 1000)
            if DONE in text:
                return PersonaTurn(None, True, usage, ms)
            if not text:
                raise PersonaError("empty message")
            return PersonaTurn(text, False, usage, ms)
        raise PersonaError("retries exhausted")

    def _text(self, data: dict) -> str:
        if self.api != "responses":
            return (data["choices"][0]["message"].get("content") or "").strip()
        if data.get("status") not in (None, "completed"):
            raise PersonaError(f"response {data.get('status')}")
        parts = [c.get("text", "") for o in data.get("output") or [] if o.get("type") == "message"
                 for c in o.get("content") or [] if c.get("type") == "output_text"]
        return "".join(parts).strip()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="One persona call with a synthetic card (owner-approved smoke test)")
    p.add_argument("--smoke", action="store_true", required=True)
    p.add_argument("--live", action="store_true")
    a = p.parse_args(argv)
    if not a.live:
        print("refusing: a persona call is a live call; rerun with --live after the owner approves")
        return 2
    from evalkit.config import load_config
    from evalkit.goals import GoalCard
    cfg = load_config()
    card = GoalCard(goal_id="SMOKE", split="dev", group="account_info", language="es", customer_id="CLI-SMOKE",
                    country="México", segment="Retail",
                    persona={"verbosity": "normal", "vagueness": "low", "patience": "normal"},
                    hidden_goal="You want to know the balance of your credit card ending in 4242.",
                    revealable_facts={"last4": "4242"}, expected={}, allowed_ids=[])
    t = PersonaClient.from_config(cfg["persona"]).next(card, [])
    print(json.dumps({"model": cfg["persona"]["model"], "text": t.text, "done": t.done, "usage": t.usage,
                      "latency_ms": t.latency_ms, "violations": check_message(card, t.text or "")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
