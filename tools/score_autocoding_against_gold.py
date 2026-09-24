#!/usr/bin/env python3
"""Score Jev, slow coder, judge, and final route against completed blind human gold."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

DIMS = ["request_type", "verdict_given", "proposal_alignment", "epistemic_openness", "gate_tone"]
DEFAULT = Path(__file__).resolve().parent.parent / "model-comparison/permission-gate-pilot/2026-09-23T08-49-00Z/coding-v1"


def load_gold(path: Path):
    gold = {}
    for row in csv.DictReader(path.open(encoding="utf-8")):
        if not all(row.get(d, "").strip() for d in DIMS):
            continue
        gold[(row["blind_id"], int(row["turn"]))] = row
    return gold


def label(record, source, dim):
    if source == "jev": return record["jev"]["codes"][dim]["label"]
    if source == "slow": return (record["slow"]["codes"] or {}).get(dim)
    if source == "judge": return ((record.get("judge") or {}).get("codes") or {}).get(dim)
    if source == "final": return (record["final"]["codes"] or {}).get(dim)
    raise ValueError(source)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--analysis-dir",type=Path,default=DEFAULT); ap.add_argument("--codes-dir",default="autocodes"); args=ap.parse_args()
    gold=load_gold(args.analysis_dir/"human_gold_template.csv")
    if not gold: raise SystemExit("No complete human-gold rows. Fill the blinded template first.")
    records={}
    for p in (args.analysis_dir/args.codes_dir).glob("B*__t*.json"):
        d=json.loads(p.read_text()); records[(d["blind_id"],d["turn"])]=d
    report={"gold_units":len(gold),"sources":{}}
    for source in ["jev","slow","judge","final"]:
        bydim={}
        for dim in DIMS:
            available=correct=0; cm=Counter()
            for key,g in gold.items():
                r=records.get(key)
                if not r: continue
                pred=label(r,source,dim)
                if pred is None: continue
                available+=1; correct+=pred==g[dim]; cm[(g[dim],pred)]+=1
            bydim[dim]={"n":available,"accuracy":correct/available if available else None,"confusion":{f"{a} -> {b}":n for (a,b),n in cm.items()}}
        report["sources"][source]=bydim
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
