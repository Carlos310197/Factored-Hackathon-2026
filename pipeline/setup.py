"""Run infra/snowflake/*.sql with ${TOKEN} substitution.

Account objects (warehouse, roles, databases, schemas, stages) are Terraform-managed; these scripts only hold
tables whose columns evolve on purpose (ENABLE_SCHEMA_EVOLUTION), which Terraform would fight.
"""
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv

from pipeline.connect import get_connection

TOKEN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def render(sql: str, params: Mapping[str, str]) -> str:
    return TOKEN.sub(lambda m: params[m.group(1)], sql)


def split_statements(sql: str) -> list[str]:
    lines = [l for l in sql.splitlines() if not l.strip().startswith("--")]
    out, buf = [], []
    for line in lines:
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if stmt:
                out.append(stmt)
            buf = []
    return out


def run_script(conn, path: Path, params: Mapping[str, str]) -> int:
    cur = conn.cursor()
    stmts = split_statements(render(path.read_text(), params))
    for s in stmts:
        cur.execute(s)
    return len(stmts)


if __name__ == "__main__":
    load_dotenv()
    params = {"DATABASE": os.environ.get("SETUP_DATABASE", "LATAM_BANK")}
    with get_connection() as conn:
        for name in sys.argv[1:]:
            n = run_script(conn, Path("infra/snowflake") / name, params)
            print(f"{name}: {n} statements")
