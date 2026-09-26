#!/usr/bin/env python3
"""Every percentage and thousands-separated number in the submission documents must be one of the
generated numbers in artifacts/report/numbers.json (CLAUDE.md: never claim an unmeasured number).
A line can opt out with `<!-- numbers-ok: <reason> -->`, for example an amount typed on camera.
Usage: scripts/check-numbers.py [files...]  (default: README.md and docs/video/*.md)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?%)")


def main(argv: list[str]) -> int:
    doc = json.loads((ROOT / "artifacts" / "report" / "numbers.json").read_text())
    allowed: set[str] = set()
    for entry in doc["numbers"].values():
        allowed.update(TOKEN.findall(str(entry["text"])))
    files = [Path(a) for a in argv] or [
        ROOT / "README.md",
        *sorted((ROOT / "docs" / "video").glob("*.md")),
    ]
    bad = 0
    for f in files:
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if "numbers-ok:" in line:
                continue
            for tok in TOKEN.findall(line):
                if tok not in allowed:
                    print(
                        f"{f.relative_to(ROOT)}:{i}: {tok} is not in artifacts/report/numbers.json"
                    )
                    bad += 1
    print("check-numbers: clean" if not bad else f"check-numbers: {bad} unmeasured number(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
