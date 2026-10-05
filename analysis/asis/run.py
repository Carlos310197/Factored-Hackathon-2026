"""python -m asis.run: as-is metrics, artifacts, reconciliation, charts and report (evaluation spec §3)."""
import argparse
import json
from datetime import date
from pathlib import Path

from asis.artifacts import detect_all
from asis.charts import render_all
from asis.load import WINDOW, connect
from asis.metrics import collect
from asis.reconcile import reconcile
from asis.report import render


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("../data/data"))
    p.add_argument("--out", type=Path, default=Path("asis/out"))
    p.add_argument("--reports", type=Path, default=Path("../reports"))
    p.add_argument("--curated-counts", type=Path)
    p.add_argument("--date", default=date.today().isoformat())
    a = p.parse_args(argv)
    c = connect(a.data)
    metrics = collect(c)
    arts = detect_all(c)
    curated = json.loads(a.curated_counts.read_text(encoding="utf-8")) if a.curated_counts else None
    recon = reconcile(metrics, curated)
    if recon["status"] == "mismatch":
        print(json.dumps(recon, indent=2))
        print("reconciliation mismatch: outputs not written")
        return 1
    a.out.mkdir(parents=True, exist_ok=True)
    doc = {"meta": {"window": list(WINDOW), "source": "data/data (organizer drop; backup prefix never read)",
                    "generated_for": a.date},
           "metrics": metrics, "artifacts": arts, "reconciliation": recon}
    (a.out / "asis_metrics.json").write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
    figures = render_all(metrics, a.reports / "figures")
    (a.reports / f"asis-{a.date}.md").write_text(render(metrics, arts, recon, a.date, figures), encoding="utf-8")
    print(f"wrote {a.out / 'asis_metrics.json'} and {a.reports / f'asis-{a.date}.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
