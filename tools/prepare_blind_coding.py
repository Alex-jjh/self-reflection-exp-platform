#!/usr/bin/env python3
"""Create a condition/model-blinded coding package from a frozen pilot run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN = ROOT / "model-comparison" / "permission-gate-pilot" / "2026-09-23T08-49-00Z"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_and_verify_run(run_dir: Path) -> tuple[list[tuple[Path, dict[str, Any]]], dict[str, Any]]:
    freeze_path = run_dir / "FROZEN_ANALYSIS_INPUT.json"
    if not freeze_path.exists():
        raise RuntimeError("run is not frozen: missing FROZEN_ANALYSIS_INPUT.json")
    freeze = read_json(freeze_path)
    expected = freeze.get("conversation_sha256", {})
    if not expected:
        raise RuntimeError("freeze file has no conversation checksums")
    records = []
    for name, digest in sorted(expected.items()):
        path = run_dir / name
        if not path.exists() or sha256_file(path) != digest:
            raise RuntimeError(f"frozen input checksum mismatch: {name}")
        record = read_json(path)
        if record.get("status") != "clean" or len(record.get("transcript", [])) != 8:
            raise RuntimeError(f"invalid frozen conversation: {name}")
        records.append((path, record))
    if len(records) != freeze.get("conversation_count"):
        raise RuntimeError("frozen conversation count mismatch")
    return records, freeze


def prepare(run_dir: Path, analysis_dir: Path, seed: int) -> dict[str, Any]:
    records, freeze = load_and_verify_run(run_dir)
    if analysis_dir.exists():
        raise RuntimeError(f"analysis directory already exists: {analysis_dir}")
    blind_dir = analysis_dir / "blind"
    blind_dir.mkdir(parents=True)

    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    mapping = []
    cell_candidates: dict[tuple[str, str, str], list[str]] = {}
    for index, (source_path, record) in enumerate(shuffled, 1):
        blind_id = f"B{index:03d}"
        spec = record["spec"]
        blind = {
            "schema_version": 1,
            "blind_id": blind_id,
            "language": "zh",
            "turns": [
                {
                    "turn": turn["turn"],
                    "user": turn["user"],
                    "assistant": turn["assistant"],
                }
                for turn in record["transcript"]
            ],
        }
        atomic_json(blind_dir / f"{blind_id}.json", blind)
        item = {
            "blind_id": blind_id,
            "source_file": source_path.name,
            "generator_model": spec["model"],
            "track": spec["track"],
            "condition": spec["condition"],
            "repeat": spec["repeat"],
        }
        mapping.append(item)
        key = (spec["model"], spec["track"], spec["condition"])
        cell_candidates.setdefault(key, []).append(blind_id)

    # One blinded conversation per 3×2×2 cell for a 20% human-gold subset.
    chooser = random.Random(seed + 1)
    gold_ids = sorted(chooser.choice(ids) for _, ids in sorted(cell_candidates.items()))
    mapping_by_id = {item["blind_id"]: item for item in mapping}
    private_mapping = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "source_tree_sha256": freeze["conversation_tree_sha256"],
        "blind_seed": seed,
        "mapping": mapping,
        "human_gold_blind_ids": gold_ids,
    }
    atomic_json(analysis_dir / "private_mapping.json", private_mapping)

    with (analysis_dir / "human_gold_template.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "blind_id", "turn", "request_type", "verdict_given",
            "proposal_alignment", "epistemic_openness", "gate_tone",
            "rationale", "evidence_quote", "adjudicator",
        ])
        for blind_id in gold_ids:
            for turn in (6, 7, 8):
                writer.writerow([blind_id, turn, "", "", "", "", "", "", "", ""])

    public_manifest = {
        "schema_version": 1,
        "source_run_id": run_dir.name,
        "source_tree_sha256": freeze["conversation_tree_sha256"],
        "blind_seed": seed,
        "conversation_count": len(mapping),
        "coded_turns": [6, 7, 8],
        "human_gold_count": len(gold_ids),
        "human_gold_blind_ids": gold_ids,
        "blinding": "model, condition, repeat, source filename withheld from coder inputs",
    }
    atomic_json(analysis_dir / "BLIND_MANIFEST.json", public_manifest)
    return public_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--analysis-name", default="coding-v1")
    parser.add_argument("--seed", type=int, default=20260923)
    args = parser.parse_args()
    analysis_dir = args.run_dir / args.analysis_name
    result = prepare(args.run_dir, analysis_dir, args.seed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"BLIND PACKAGE READY: {analysis_dir}")


if __name__ == "__main__":
    main()
