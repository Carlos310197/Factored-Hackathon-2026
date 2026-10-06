import json
from collections import Counter
from pathlib import Path

PRIVATE_FIELDS = ("customer_id", "product_id")


def public(t: dict) -> dict:
    """Committed dataset files keep transaction fields only: no customer or product ids."""
    return {k: v for k, v in t.items() if k not in PRIVATE_FIELDS}


def country_of(candidates: list[dict]) -> str | None:
    """The customer's most frequent transaction country: a proxy, since histories carry no customer attributes."""
    c = Counter(t.get("transaction_country") for t in candidates if t.get("transaction_country"))
    return c.most_common(1)[0][0] if c else None


def save_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
