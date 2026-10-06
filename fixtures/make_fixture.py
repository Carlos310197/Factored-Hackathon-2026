"""SYNTHETIC fixture drop for the transactions table. Nothing here comes from the organizer dataset."""
import csv
from pathlib import Path

COLUMNS = ["transaction_id", "transaction_date", "process_date", "product_id", "customer_id", "transaction_type",
           "transaction_category", "amount", "currency", "amount_usd", "channel", "branch_id", "merchant_name",
           "merchant_category", "transaction_country", "transaction_city", "transaction_status", "response_code",
           "is_fraud", "fraud_score", "latitude", "longitude"]


def row(i: int, day: int, status: str = "Approved", amount: str | None = None, extra: dict | None = None) -> dict:
    r = {
        "transaction_id": f"FIX-{day:02d}-{i:04d}", "transaction_date": f"2026-06-{day:02d} 10:{i % 60:02d}:00",
        "process_date": f"2026-06-{day:02d}", "product_id": "PRD-FIXTURE0001", "customer_id": "CUS-FIXTURE0001",
        "transaction_type": "Purchase", "transaction_category": "Food", "amount": amount or f"{100 + i}.00",
        "currency": "MXN", "amount_usd": f"{(100 + i) / 17:.2f}", "channel": "POS", "branch_id": "",
        "merchant_name": "Tienda Fixture", "merchant_category": "5411", "transaction_country": "Mexico",
        "transaction_city": "CDMX", "transaction_status": status, "response_code": "00" if status == "Approved" else "05",
        "is_fraud": "False", "fraud_score": "3.5", "latitude": "19.43", "longitude": "-99.13",
    }
    if extra:
        r.update(extra)
    return r


def _write(path: Path, rows: list[dict], columns: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)
    return path


def _path(out: Path, day: int) -> Path:
    return out / "transactions" / "year=2026" / "month=06" / f"day={day:02d}" / f"transactions_202606{day:02d}.csv"


# the one customer and product every fixture transaction points at, so the relationships tests can run
CUSTOMER = {"customer_id": "CUS-FIXTURE0001", "document_number": "00000000", "document_type": "DNI", "first_name": "Fixture",
            "last_name": "Cliente", "date_of_birth": "1990-01-01", "gender": "F", "email": "fixture@example.com",
            "mobile_phone": "+520000000000", "landline_phone": "", "address": "Calle Falsa 123", "city": "CDMX", "state": "CDMX",
            "country": "Mexico", "postal_code": "00000", "detected_accent": "mexicano", "segment": "Mass", "credit_score": "700",
            "estimated_monthly_income": "20000", "occupation": "Engineer", "marital_status": "Single",
            "education_level": "University", "registration_date": "2024-01-01 09:00:00", "registration_branch_id": "",
            "customer_status": "Active", "last_updated": "2026-06-01 09:00:00", "accepts_marketing": "False"}
PRODUCT = {"product_id": "PRD-FIXTURE0001", "customer_id": "CUS-FIXTURE0001", "product_type": "Tarjeta Débito",
           "product_number": "0000000000001234", "currency": "MXN", "current_balance": "1000.00", "credit_limit": "",
           "interest_rate": "", "opening_date": "2024-01-01", "expiration_date": "2029-01-01", "opening_branch_id": "",
           "product_status": "Active", "opening_channel": "Branch", "has_linked_app": "True", "days_past_due": "0",
           "last_transaction_date": "2026-06-17 10:00:00", "last_updated": "2026-06-01 09:00:00"}


def write_phase(out: Path, phase: int) -> list[Path]:
    if phase == 1:
        return [_write(_path(out, 17), [row(i, 17) for i in range(20)], COLUMNS)]
    if phase == 3:  # dimensions only
        return [_write(out / "customers.csv", [CUSTOMER], list(CUSTOMER)), _write(out / "products.csv", [PRODUCT], list(PRODUCT))]
    if phase == 4:  # day 22: one valid row, one orphan FK (a product that does not exist)
        return [_write(_path(out, 22), [row(0, 22), row(1, 22, extra={"product_id": "PRD-ORPHAN0001"})], COLUMNS)]
    # restated day 17: 3 rows changed, key 19 removed (the restated file is the truth for its partition)
    d17 = [row(i, 17, status="Reversed" if i < 3 else "Approved") for i in range(19)]
    d17 += d17[:5]  # 5 exact duplicates of already-present keys (same file), incl. the restated ones
    files = [
        _write(_path(out, 17), d17, COLUMNS),
        _write(_path(out, 18), [row(i, 18) for i in range(10)], COLUMNS),
        _write(_path(out, 19), [row(i, 19, extra={"merchant_country": "MX"}) for i in range(5)], COLUMNS + ["merchant_country"]),
        _write(_path(out, 20), [row(0, 20, amount="N/A")] + [row(i, 20) for i in range(1, 5)], COLUMNS),
        _write(_path(out, 21), [], COLUMNS),
    ]
    return files


if __name__ == "__main__":
    import sys
    for p in write_phase(Path(sys.argv[1]), int(sys.argv[2])):
        print(p)
