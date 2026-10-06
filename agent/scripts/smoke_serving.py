import argparse
import json
import os
import statistics
import time

from bankagent.context import SCOPE_READ, SessionContext
from bankagent.data.serving import ServingData
from bankagent.tools.read import ReadTools

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, default=10)
    a = ap.parse_args()
    sd = ServingData(os.environ["SERVING_URI"], os.environ.get("AWS_REGION", "us-east-1"))
    p = sd.pointer()
    ids = [r["customer_id"] for r in sd.query(p.run_id, "dim_customer", "1=1", [], "customer_id")][:: 997][: a.customers]
    tools, times = ReadTools(sd), []
    for cid in ids:
        ctx = SessionContext(cid, "S-smoke", frozenset({SCOPE_READ}), "es", 0)
        start = time.monotonic()
        tools.list_transactions(ctx, p.run_id, p.max_process_date)
        tools.get_accounts(ctx, p.run_id, p.max_process_date)
        times.append((time.monotonic() - start) * 1000)
    times.sort()
    print(json.dumps({"serving_uri": os.environ["SERVING_URI"], "run_id": p.run_id, "n": len(times),
                      "p50_ms": round(statistics.median(times)), "p95_ms": round(times[int(0.95 * (len(times) - 1))])}))
