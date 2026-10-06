"""Compare extract models on the resolver test messages. Calls Bedrock."""
import argparse
import dataclasses
import json
import time
from pathlib import Path

from bankagent.decisions.understand import matches_mentions
from bankagent.llm.client import LLMError, make_bedrock_client
from bankagent.llm.config import load_models
from bankagent.llm.extract import extract
from bankagent.resolver.records import load_jsonl

AGENT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--rows", default=str(AGENT / "resolver" / "data" / "test_v1.jsonl"))
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = dataclasses.replace(load_models()["extract"], model=a.model)
    client, rows, out = make_bedrock_client(a.region), load_jsonl(Path(a.rows)), []
    for r in rows:
        t0 = time.monotonic()
        try:
            ex, call = extract(client, cfg, r["message"], r["anchor"], [])
            m = ex.mentions
            out.append({"case_id": r["case_id"], "slice": r["slice"], "ok": True, "ms": int((time.monotonic() - t0) * 1000),
                        "out_tokens": call.usage.get("output_tokens"), "has_mentions": any(m.values()),
                        "consistent": None if r["slice"] == "nil" else matches_mentions(r["target"], m)})
        except LLMError as e:
            out.append({"case_id": r["case_id"], "slice": r["slice"], "ok": False,
                        "ms": int((time.monotonic() - t0) * 1000), "error": str(e)[:60]})
    Path(a.out or f"extract_{a.model}.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
