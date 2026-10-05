"""DynamoDB needs Decimal for numbers; the rest of the app uses float/int. None values are dropped."""
from decimal import Decimal


def to_dynamo(v):
    if isinstance(v, bool) or v is None or isinstance(v, (int, str)):
        return v
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, dict):
        return {k: to_dynamo(x) for k, x in v.items() if x is not None}
    if isinstance(v, (list, tuple)):
        return [to_dynamo(x) for x in v]
    return v


def from_dynamo(v):
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, dict):
        return {k: from_dynamo(x) for k, x in v.items()}
    if isinstance(v, list):
        return [from_dynamo(x) for x in v]
    return v
