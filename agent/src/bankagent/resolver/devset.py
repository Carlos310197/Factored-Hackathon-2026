"""Dev set (resolver spec §5.3): the simulator picks history, target and description style; the dev_writer model
writes the customer's ES/PT message from those details only; the real extract reads the message. The label is known
by construction. Committed rows keep transaction fields only (no customer or product ids)."""
import random

from bankagent.llm.client import LLMError, call_json
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
Return JSON {"message": "..."}."""
WRITER_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["message"],
                 "properties": {"message": {"type": "string"}}}


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
        out.append(f"the amount: {prefix} {m['amount']:g}{cur}")
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


def write_message(client, cfg: RoleConfig, case: dict, lang: str, flavor: str):
    goal = ("they want to dispute or complain about this charge" if flavor == "dispute"
            else "they ask what happened with this transaction")
    user = (f"language: {LANG_NAMES[lang]}\ngoal: {goal}\ndetails:\n" + "\n".join(f"- {d}" for d in details_en(case)))
    return call_json(client, cfg, WRITER_SYSTEM, user, WRITER_SCHEMA)


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
