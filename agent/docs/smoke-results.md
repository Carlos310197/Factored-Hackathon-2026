# Live smoke results

## Jev (TypeSafe direct, jev-1.13.0) — 2026-10-04
Synthetic request from `scripts/smoke_jev.py`.
```json
{
  "model": "jev-1.13.0",
  "latency_ms": 583,
  "usage": {
    "input_tokens": 757,
    "output_tokens": 114
  },
  "answers": {
    "intent": {
      "label": "dispute_charge",
      "probabilities": {
        "account_info": 0.0,
        "dispute_charge": 1.0,
        "unclear": 0.0
      },
      "confidence": 1.0
    },
    "target_transaction": {
      "label": "ambiguous",
      "probabilities": {
        "c2": 0.0,
        "c3": 0.0,
        "c1": 0.01,
        "ambiguous": 0.99
      },
      "confidence": 0.99
    },
    "injection_attempt": {
      "p": 0.03
    }
  }
}
```
