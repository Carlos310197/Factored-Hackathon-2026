"""Time-sortable identifiers for disputes, handoffs, receipts and turns."""
import secrets
import time


def new_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000):013d}{secrets.token_hex(4).upper()}"
