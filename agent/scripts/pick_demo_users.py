import argparse
from pathlib import Path

from bankagent.data.demo_users import build_users, select_demo_customers, write_users

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--serving", default=".serving")
    ap.add_argument("--out", default="config/demo_users.yaml")
    a = ap.parse_args()
    customers = select_demo_customers(Path(a.serving), {"México": 8, "Colombia": 6, "Argentina": 6})
    users = build_users(customers)
    write_users(Path(a.out), users)
    for u in users:
        print(u["username"], u["customer_id"], u["lang"])
