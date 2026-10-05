"""Live smoke test: one extract call and one compose call on Bedrock with SYNTHETIC input.
Run only with the owner's approval:  AWS_PROFILE=<profile> uv run python scripts/smoke_bedrock.py"""
import json
import os

from bankagent.llm.client import make_bedrock_client
from bankagent.llm.compose import compose
from bankagent.llm.config import load_models
from bankagent.llm.extract import extract

if __name__ == "__main__":
    models = load_models()
    client = make_bedrock_client(os.environ.get("AWS_REGION", "us-east-1"))
    ex, c1 = extract(client, models["extract"], "Me cobraron dos veces la suscripción de streaming del 10 de junio",
                     "2026-06-17", [])
    receipts = [{"receipt_id": "RCP-SMOKE1", "source": "fct_transaction", "as_of": "2026-06-17",
                 "data": {"merchant_name": "StreamCo", "process_date": "2026-06-10", "transaction_status": "Approved",
                          "amount": 15.99, "currency": "USD"}}]
    out, c2 = compose(client, models["compose"], {"kind": "answer"}, receipts, "es")
    print(json.dumps({"extract": {"model": c1.model, "latency_ms": c1.latency_ms, "usage": c1.usage, "output": vars(ex)},
                      "compose": {"model": c2.model, "latency_ms": c2.latency_ms, "usage": c2.usage,
                                  "reply": out.reply_text, "claims": out.claims}}, indent=2, ensure_ascii=False))
