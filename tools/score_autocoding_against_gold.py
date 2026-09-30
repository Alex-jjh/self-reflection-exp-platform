#!/usr/bin/env python3
"""Score Jev, slow coder, judge and final route against a completed reference CSV.

The reference is either the human anchor (Alex's codes of the 12 anchor units,
research-repo D-019) or the 36-unit AI reference (Claude's blind codes,
`coding-v1/ai_reference_claude_blind.csv`). The AI reference is AI codes, not
human codes, so the report gives agreement with the named file, not accuracy
against ground truth. The CSV header is the one written by
`prepare_blind_coding.py` and by the HTML workbook (`build_human_review_workbook.py`).

If the codes directory has a CODING_LOCK.json (written by run_matrix_autocoding.py),
only records whose rubric and script hashes match the lock are scored; the
others are listed under `stale_units_excluded`. A directory without a lock
(for example coding-v1/autocodes/) is scored as it is.

Usage:
    python tools/score_autocoding_against_gold.py --reference human_anchor_alex.csv --codes-dir autocodes-v2.1
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

DIMS = ["request_type", "verdict_given", "proposal_alignment", "epistemic_openness", "gate_tone"]
SOURCES = ["jev", "slow", "judge", "final"]
DEFAULT = Path(__file__).resolve().parent.parent / "model-comparison/permission-gate-pilot/2026-09-23T08-49-00Z/coding-v1"
LOCK_NAME = "CODING_LOCK.json"  # as in run_matrix_autocoding.py


def load_reference(path: Path) -> tuple[dict[tuple[str, int], dict[str, str]], int]:
    """Return (complete rows keyed by (blind_id, turn), number of incomplete rows skipped)."""
    rows = {}
    skipped = 0
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not all((row.get(d) or "").strip() for d in DIMS):
                skipped += 1
                continue
            rows[(row["blind_id"], int(row["turn"]))] = row
    return rows, skipped


def label(record, source, dim):
    if source == "jev": return record["jev"]["codes"][dim]["label"]
    if source == "slow": return (record["slow"]["codes"] or {}).get(dim)
    if source == "judge": return ((record.get("judge") or {}).get("codes") or {}).get(dim)
    if source == "final": return (record["final"]["codes"] or {}).get(dim)
    raise ValueError(source)


def lock_hashes(codes_dir: Path) -> dict | None:
    """Rubric and script hashes from the directory's lock, or None if it has no lock."""
    path = codes_dir / LOCK_NAME
    if not path.exists():
        return None
    files = json.loads(path.read_text(encoding="utf-8")).get("files") or {}
    return {
        "rubric_sha256": (files.get("rubric") or {}).get("sha256"),
        "script_sha256": (files.get("script") or {}).get("sha256"),
    }


def score(reference_path: Path, codes_dir: Path) -> dict:
    reference, skipped = load_reference(reference_path)
    if not reference:
        raise SystemExit(f"No complete rows in {reference_path}: every row needs all five labels.")
    lock = lock_hashes(codes_dir)
    records, stale = {}, []
    for p in codes_dir.glob("B*__t*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        key = (d["blind_id"], d["turn"])
        if lock and any(d.get(field) != value for field, value in lock.items()):
            # Coded under other instructions than the lock: never mixed into the scores.
            if key in reference:
                stale.append(f"{key[0]} t{key[1]}")
            continue
        records[key] = d
    matched = [records[key] for key in reference if key in records]
    # Records written before schema 2 carry no rubric or script hash; they show as null.
    hashes = Counter(
        (r.get("rubric_version"), r.get("rubric_sha256"), r.get("script_sha256")) for r in matched
    )
    report = {
        "reference_file": reference_path.name,
        "reference_units": len(reference),
        "incomplete_rows_skipped": skipped,
        "codes_dir": codes_dir.name,
        "codes_lock": lock,
        "units_without_autocode": sorted(
            f"{b} t{t}" for (b, t) in reference
            if (b, t) not in records and f"{b} t{t}" not in stale
        ),
        "stale_units_excluded": sorted(stale),
        "autocode_rubrics": [
            {"rubric_version": version, "rubric_sha256": rubric, "script_sha256": script, "units": n}
            for (version, rubric, script), n in sorted(hashes.items(), key=str)
        ],
        "sources": {},
    }
    for source in SOURCES:
        bydim = {}
        for dim in DIMS:
            available = agree = 0
            cm = Counter()
            for key, ref in reference.items():
                r = records.get(key)
                if not r:
                    continue
                pred = label(r, source, dim)
                if pred is None:
                    continue
                available += 1
                agree += pred == ref[dim]
                cm[(ref[dim], pred)] += 1
            bydim[dim] = {
                "n": available,
                "agreement": agree / available if available else None,
                "confusion": {f"{a} -> {b}": n for (a, b), n in cm.items()},
            }
        report["sources"][source] = bydim
    return report


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis-dir", type=Path, default=DEFAULT)
    ap.add_argument("--codes-dir", default="autocodes", help="autocode directory inside --analysis-dir")
    ap.add_argument(
        "--reference", "--gold", dest="reference", required=True,
        help="completed reference CSV inside --analysis-dir (human anchor or AI reference); "
             "--gold is kept as an alias",
    )
    args = ap.parse_args(argv)
    report = score(args.analysis_dir / args.reference, args.analysis_dir / args.codes_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
