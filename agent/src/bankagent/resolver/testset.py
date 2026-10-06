import csv
import hashlib
import json
import random
from pathlib import Path

from bankagent.decisions.understand import describe_txn
from bankagent.llm.config import RoleConfig
from bankagent.llm.client import LLMError
from bankagent.llm.extract import extract
from bankagent.resolver.records import country_of, public
from bankagent.resolver.histories import History
from bankagent.resolver.simulate import simulate

QUOTAS = {"hard": 75, "easy": 60, "nil": 15}
SHEET_COLUMNS = ("case_id", "lang", "instruction", "describe_this", "style_hint", "candidates", "message")
MERCHANT_HINTS = {"exact": "name the merchant", "noisy": "name the merchant loosely (a typo or no accents)",
                  "absent": "don't name the merchant"}
AMOUNT_HINTS = {"exact": "give the exact amount", "rounded": "round the amount", "approx": "say roughly how much",
                "usd": "give the amount in US dollars", "absent": "don't say the amount"}
DATE_HINTS = {"exact": "give the date", "off_by_one": "get the date wrong by one day", "absent": "don't say when"}


def style_hint(style: dict) -> str:
    if style.get("no_detail"):
        return "give no details: just say there is a charge you want to ask about"
    parts = [MERCHANT_HINTS.get(style.get("merchant")), AMOUNT_HINTS.get(style.get("amount"))]
    parts.append(f"say when loosely ('{style['date_label']}')" if style.get("date") == "relative"
                 else DATE_HINTS.get(style.get("date")))
    if style.get("type_hint") == "present":
        parts.append("say what kind of transaction it was")
    if style.get("channel_hint") == "present":
        parts.append("say where it happened (ATM, shop, app, web, branch)")
    if style.get("city") == "present":
        parts.append("mention the city")
    return "; ".join(p for p in parts if p)


def make_test_sheet(histories: list[History], sim_cfg: dict, seed: int, quotas: dict = QUOTAS) -> list[dict]:
    cases = simulate(histories, sim_cfg | {"extract_error": 0.0}, seed)
    taken = {k: 0 for k in quotas}
    out = []
    for c in cases:
        k = c["slice"]
        if taken.get(k, 0) >= quotas.get(k, 0):
            continue
        lang = ("es", "pt")[taken[k] % 2]
        taken[k] += 1
        instruction = ("Describe this transaction. It is NOT in the list below: write as if you believe it is yours."
                       if k == "nil" else "Describe this transaction (it is in the list below).")
        out.append({"case_id": c["case_id"], "set": "test", "lang": lang, "slice": k, "anchor": c["anchor"],
                    "country": country_of(c["candidates"]), "target_id": c["target_id"], "target": public(c["target"]),
                    "candidates": [public(t) for t in c["candidates"]], "style": c["style"],
                    "style_hint": style_hint(c["style"]), "instruction": instruction})
        if all(taken[q] >= quotas[q] for q in quotas):
            break
    return out


def write_sheet(cases: list[dict], stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".json").write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    with stem.with_suffix(".csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
        w.writeheader()
        for c in cases:
            w.writerow({"case_id": c["case_id"], "lang": c["lang"], "instruction": c["instruction"],
                        "describe_this": describe_txn(c["target"]), "style_hint": c["style_hint"],
                        "candidates": "\n".join(f"{i + 1}) {describe_txn(t)}" for i, t in enumerate(c["candidates"])),
                        "message": ""})


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_sheet(path: Path) -> list[dict]:
    """Rows of a sheet a person edited: tolerates a byte-order mark and ';' or tab delimiters (Excel, Sheets)."""
    text = Path(path).read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(text.split("\n", 1)[0], delimiters=",;\t")
    return list(csv.DictReader(text.splitlines(keepends=True), dialect=dialect))


def read_messages(csv_path: Path) -> dict[str, str]:
    return {r["case_id"].strip(): (r.get("message") or "").strip() for r in read_sheet(csv_path)}


def ingest_test_set(stem: Path, completed_csv: Path, client, models: dict[str, RoleConfig]) -> tuple[list[dict], str]:
    """An extract failure keeps the row with empty mentions, as the live agent would."""
    cases = json.loads(stem.with_suffix(".json").read_text(encoding="utf-8"))
    messages = read_messages(completed_csv)
    missing = [c["case_id"] for c in cases if not messages.get(c["case_id"])]
    if missing:
        raise ValueError(f"{len(missing)} test cases have no message: {missing[:5]}")
    rows = []
    for c in cases:
        msg = messages[c["case_id"]]
        try:
            ex, call = extract(client, models["extract"], msg, c["anchor"], [])
            extraction = {"mentions": ex.mentions, "language_detected": ex.language_detected,
                          "english_gloss": ex.english_gloss}
            versions = {"extract": [call.model, call.prompt_version]}
        except LLMError as e:
            extraction = {"mentions": {}, "language_detected": None, "english_gloss": None, "error": str(e)}
            versions = {"extract": [models["extract"].model, models["extract"].prompt_version]}
        rows.append({k: v for k, v in c.items() if k not in ("instruction",)} |
                    {"message": msg, "extraction": extraction, "versions": versions})
    return rows, sha256_file(completed_csv)


def make_ceiling_sheet(rows: list[dict], n: int, seed: int, path: Path) -> list[str]:
    picked = random.Random(seed).sample(rows, min(n, len(rows)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=("case_id", "message", "candidates", "pick"))
        w.writeheader()
        for r in picked:
            w.writerow({"case_id": r["case_id"], "message": r["message"], "pick": "",
                        "candidates": "\n".join(f"{i + 1}) {describe_txn(t)}" for i, t in enumerate(r["candidates"]))})
    return [r["case_id"] for r in picked]


def read_ceiling(path: Path, rows: list[dict]) -> dict[str, str | None]:
    by_id = {r["case_id"]: r for r in rows}
    out = {}
    for r in read_sheet(path):
        case_id, pick = r["case_id"].strip(), (r.get("pick") or "").strip().lower()
        if not pick:
            raise ValueError(f"ceiling sheet: no pick for {case_id}")
        cands = by_id[case_id]["candidates"]
        out[case_id] = None if pick == "none" else cands[int(pick) - 1]["transaction_id"]
    return out
