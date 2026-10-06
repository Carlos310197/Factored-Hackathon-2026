"""Customer split rule, identical to the resolver's split: first byte of sha256(customer_id) mod 10."""
import hashlib


def customer_split(customer_id: str) -> str:
    bucket = hashlib.sha256(customer_id.encode("utf-8")).digest()[0] % 10
    return "train" if bucket <= 7 else ("dev" if bucket == 8 else "test")
