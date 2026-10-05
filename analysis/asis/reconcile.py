"""Reconciliation with the curated marts (evaluation spec §3.4). The curated numbers come from reconcile.sql."""
TOLERANCE = 0.001
KEYS = {"interactions_n": "demand.total", "complaints_n": "complaints.total",
        "transaccional_fcr": "quality.Transaccional.fcr"}


def reconcile(metrics: dict, curated: dict | None) -> dict:
    if curated is None:
        return {"status": "not reconciled", "checks": []}
    checks = []
    for ckey, mkey in KEYS.items():
        ours, theirs = metrics[mkey]["value"], float(curated[ckey])
        diff = abs(ours - theirs) / max(abs(theirs), 1e-9)
        checks.append({"key": ckey, "ours": ours, "curated": theirs, "rel_diff": round(diff, 6), "ok": diff <= TOLERANCE})
    return {"status": "reconciled" if all(c["ok"] for c in checks) else "mismatch", "checks": checks}
