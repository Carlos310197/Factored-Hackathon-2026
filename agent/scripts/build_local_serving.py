"""Dev only: build agent/.serving from the organizer CSVs."""
import argparse
import json
from pathlib import Path

from bankagent.data.local_build import build_local_serving

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="../data/data")
    ap.add_argument("--out", default=".serving")
    ap.add_argument("--since", default="2026-02-01")
    a = ap.parse_args()
    print(json.dumps(build_local_serving(Path(a.data_dir), Path(a.out), a.since), indent=2))
