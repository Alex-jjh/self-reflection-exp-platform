#!/usr/bin/env python3
"""Rebuild the canonical matrix index from all cell artifacts on disk.

Cell artifacts ({script}__{model}__{lang}__{condition}__{stamp}.json) can come
from different invocations — a full run, a next-day quota top-up, a single-cell
re-run after a fix. Per-invocation RUN__ files fragment across stamps, so this
scans every cell JSON and writes ONE canonical index:

    model-comparison/MATRIX.md

For each (script, model, lang, condition) key, the newest stamp wins; stale
duplicates are listed at the bottom so they can be pruned deliberately rather
than silently ignored.

Usage:  python tools/matrix_index.py
"""

from __future__ import annotations  # session laptop venv is 3.9

import json
import sys
from collections import defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT))

import model_compare as mc

OUT_DIR = ROOT / "model-comparison"
COND_ORDER = {"supportive": 0, "challenging": 1, "neutral": 2}


def main():
    cells = {}
    stale = []
    for f in sorted(OUT_DIR.glob("*__*__*__*__*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not {"script", "model_short", "lang", "condition", "run_stamp"} <= set(d):
            continue
        key = (d["script"], d["model_short"], d["lang"], d["condition"])
        d["_file"] = f.name
        if key in cells:
            older = min(cells[key], d, key=lambda x: x["run_stamp"])
            stale.append(older["_file"])
            if cells[key] is older:
                cells[key] = d
        else:
            cells[key] = d

    by_matrix = defaultdict(list)   # (script, lang) -> [cell]
    for (script, model, lang, cond), d in cells.items():
        by_matrix[(script, lang)].append(d)

    L = ["# Cross-model pilot — canonical matrix index\n",
         "Rebuilt by `tools/matrix_index.py` from every cell artifact on disk; "
         "newest stamp wins per cell. Per-invocation `RUN__*.md` files are "
         "superseded by this file.\n",
         "> Signal counts are lexical screening aids, not codes — read the cell "
         "transcript before repeating any number.\n"]

    for (script, lang) in sorted(by_matrix):
        rows = by_matrix[(script, lang)]
        rows.sort(key=lambda d: (d["model_short"], COND_ORDER.get(d["condition"], 9)))
        models = sorted({r["model_short"] for r in rows})
        conds = sorted({r["condition"] for r in rows}, key=lambda c: COND_ORDER.get(c, 9))
        L.append(f"\n## {script} ({lang}) — {len(rows)} cells "
                 f"({len(models)} models × {len(conds)} conditions)\n")
        L.append("| model | condition | turns | AI chars | signals | conditions rev | stamp | file |")
        L.append("|---|---|---|---|---|---|---|---|")
        for d in rows:
            if d.get("error") or not d.get("transcript"):
                L.append(f"| `{d['model_short']}` | {d['condition']} | — | — | ERROR "
                         f"| `{d.get('conditions_rev','?')}` | {d['run_stamp']} | `{d['_file']}` |")
                continue
            allt = "\n".join(t["assistant"] for t in d["transcript"])
            hits = mc.scan_signals(allt)
            n = sum(len(v) for v in hits.values())
            labels = ", ".join(f"{k}×{len(v)}" for k, v in hits.items()) or "—"
            L.append(f"| `{d['model_short']}` | {d['condition']} | {len(d['transcript'])} "
                     f"| {len(allt)} | {n} ({labels}) | `{d.get('conditions_rev','?')}` "
                     f"| {d['run_stamp']} | `{d['_file'][:-5]}.md` |")

    if stale:
        L.append("\n## Stale duplicates (superseded by a newer stamp — prune deliberately)\n")
        for s in sorted(stale):
            L.append(f"- `{s}`")

    out = OUT_DIR / "MATRIX.md"
    out.write_text("\n".join(L), encoding="utf-8")
    total = len(cells)
    errs = sum(1 for d in cells.values() if d.get("error") or not d.get("transcript"))
    print(f"MATRIX.md: {total} cells ({total-errs} clean, {errs} error) "
          f"across {len(by_matrix)} script×lang matrices; {len(stale)} stale duplicates")


if __name__ == "__main__":
    main()
