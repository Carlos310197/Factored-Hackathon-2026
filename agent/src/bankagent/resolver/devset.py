"""Dev set: the simulator picks history, target and description style; the dev_writer model
writes the customer's ES/PT message from those details only; the real extract reads the message. The label is known
by construction. Committed rows keep transaction fields only (no customer or product ids)."""
import random

import time

from bankagent.llm.client import LLMCall, LLMError
from bankagent.llm.config import RoleConfig
from bankagent.llm.extract import extract
from bankagent.resolver.histories import History
from bankagent.resolver.records import country_of, public
from bankagent.resolver.simulate import simulate

LANG_NAMES = {"es": "Spanish (Latin American)", "pt": "Brazilian Portuguese"}
FLAVORS = ("dispute", "status")
CHANNEL_PHRASES = {"atm": "at an ATM", "pos": "with the card in a shop", "app": "in the mobile app", "web": "online",
                   "branch": "at a branch"}
WRITER_SYSTEM = """You write test data: ONE realistic message a bank customer sends to LATAM Bank's support chat about
one of their transactions. Write it in the requested language, informally, like a real customer, 1-3 sentences.
Use ONLY the details listed; do not add amounts, dates, merchants, places or other facts that are not listed.
Express dates naturally ("el martes pasado", "semana passada", "el 10 de junio") and amounts as a person would.
Return only the message text, nothing else."""


def _plain(amount: float) -> str:
    """Digits only: a float's 'g' format turns 33984700 into 3.39847e+07, which the writer then copies."""
    return f"{amount:.2f}".rstrip("0").rstrip(".")


def details_en(case: dict) -> list[str]:
    m, st = case["mentions"], case["style"]
    if st.get("no_detail"):
        return ["no specific details: the customer only says there is a charge or movement they want to ask about"]
    out = []
    if m.get("merchant"):
        out.append(f'the merchant name as the customer writes it: "{m["merchant"]}"')
    if m.get("amount") is not None:
        cur = f' {m["currency"]}' if m.get("currency") else ""
        prefix = "exactly" if st.get("amount") == "exact" else "about"
        out.append(f"the amount: {prefix} {_plain(m['amount'])}{cur}")
    if m.get("date_from"):
        if st.get("date") == "relative":
            out.append(f"when: {st['date_label']} (today is {case['anchor']})")
        else:
            out.append(f"the date: {m['date_from']} (today is {case['anchor']})")
    if m.get("type_hint"):
        out.append(f"it was a {m['type_hint']}")
    if m.get("channel_hint"):
        out.append(f"it happened {CHANNEL_PHRASES[m['channel_hint']]}")
    if m.get("city"):
        out.append(f"the city: {m['city']}")
    return out or ["no specific details: the customer only says there is a charge or movement they want to ask about"]


def write_message(client, cfg: RoleConfig, case: dict, lang: str, flavor: str) -> LLMCall:
    """Plain text, not JSON: the writer's whole output is the message, and the model's JSON mode sometimes returns a
    doubled opening brace that the strict parser (rightly) rejects."""
    import openai

    goal = ("they want to dispute or complain about this charge" if flavor == "dispute"
            else "they ask what happened with this transaction")
    user = (f"language: {LANG_NAMES[lang]}\ngoal: {goal}\ndetails:\n" + "\n".join(f"- {d}" for d in details_en(case)))
    start = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=cfg.model, max_tokens=cfg.max_tokens,
            messages=[{"role": "system", "content": WRITER_SYSTEM}, {"role": "user", "content": user}])
    except openai.OpenAIError as e:
        raise LLMError(f"{type(e).__name__}: {e}") from e
    if not resp.choices or resp.choices[0].finish_reason == "length" or not resp.choices[0].message.content:
        raise LLMError("writer returned no usable text")
    text = resp.choices[0].message.content.strip().strip('"').strip()
    usage = {"input_tokens": resp.usage.prompt_tokens, "output_tokens": resp.usage.completion_tokens}
    return LLMCall({"message": text}, cfg.model, cfg.prompt_version, usage, int((time.monotonic() - start) * 1000))


def build_dev_set(histories: list[History], sim_cfg: dict, seed: int, n: int, client, models: dict[str, RoleConfig],
                  set_name: str = "dev") -> tuple[list[dict], int]:
    """Returns (rows, skipped). Simulated extract errors are switched off: the real extract makes its own."""
    cases = simulate(histories, sim_cfg | {"extract_error": 0.0}, seed)
    rng, rows, skipped = random.Random(seed), [], 0
    for case in cases:
        if len(rows) >= n:
            break
        lang, flavor = ("es", "pt")[len(rows) % 2], rng.choice(FLAVORS)
        try:
            written = write_message(client, models["dev_writer"], case, lang, flavor)
            message = written.data["message"].strip()
            ex, ex_call = extract(client, models["extract"], message, case["anchor"], [])
        except (LLMError, KeyError, AttributeError):
            skipped += 1
            continue
        rows.append({"case_id": case["case_id"], "set": set_name, "lang": lang, "flavor": flavor,
                     "slice": case["slice"], "anchor": case["anchor"], "country": country_of(case["candidates"]),
                     "target_id": case["target_id"], "target": public(case["target"]),
                     "candidates": [public(t) for t in case["candidates"]], "style": case["style"],
                     "details_en": details_en(case), "message": message,
                     "extraction": {"mentions": ex.mentions, "language_detected": ex.language_detected,
                                    "english_gloss": ex.english_gloss},
                     "versions": {"writer": [written.model, written.prompt_version],
                                  "extract": [ex_call.model, ex_call.prompt_version],
                                  "simulate": sim_cfg["version"]}})
    return rows, skipped
