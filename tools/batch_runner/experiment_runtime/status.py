"""`status`: done / failed / pending per model, last-hour throughput, ETA."""

from __future__ import annotations

import collections
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .cells import load_cells
from .contract import THROTTLED
from .store import OutputStore
from .util import blind_id, canonical_json, fmt_duration, parse_utc, sha256_hex, utc_now_iso


def compute_status(cells_path: Path, out_dir: Path, locations: Mapping[str, str],
                   prepare: Callable[..., dict] | None = None) -> dict[str, Any]:
    """``prepare`` (backend.prepare) enables the request-hash check of done cells."""
    cells = load_cells(cells_path, locations)
    store = OutputStore(out_dir)
    salt = store.load_salt(create=False) if store.key_dir.exists() else None
    done = store.done_blinds()
    failed = store.failed_blinds()
    blinds = {cell.cell_id: blind_id(salt, cell.cell_id) for cell in cells} if salt else {}

    per_model: dict[str, dict[str, Any]] = {}
    for cell in cells:
        row = per_model.setdefault(cell.model, {
            "total": 0, "done": 0, "failed": 0, "pending": 0, "ok_1h": 0, "throttled_1h": 0,
            "other_errors_1h": 0, "mean_latency_ms_1h": None, "eta_s": None,
        })
        row["total"] += 1
        blind = blinds.get(cell.cell_id)
        if blind and blind in done:
            row["done"] += 1
        elif blind and blind in failed:
            row["failed"] += 1
        else:
            row["pending"] += 1

    now = datetime.now(timezone.utc)
    latencies: dict[str, list[int]] = collections.defaultdict(list)
    for record in store.attempts_since(now - timedelta(hours=1)):
        row = per_model.get(record.get("model"))
        if row is None:
            continue
        status = record.get("status")
        if status == "ok":
            row["ok_1h"] += 1
            if isinstance(record.get("latency_ms"), int):
                latencies[record["model"]].append(record["latency_ms"])
        elif status == THROTTLED:
            row["throttled_1h"] += 1
        elif status != "duplicate":
            row["other_errors_1h"] += 1
    for model, row in per_model.items():
        if latencies[model]:
            row["mean_latency_ms_1h"] = round(sum(latencies[model]) / len(latencies[model]))
        if not row["pending"]:
            row["eta_s"] = 0
        elif row["ok_1h"]:
            row["eta_s"] = row["pending"] / row["ok_1h"] * 3600

    totals: dict[str, Any] = {key: sum(row[key] for row in per_model.values())
                              for key in ("total", "done", "failed", "pending", "ok_1h", "throttled_1h",
                                          "other_errors_1h")}
    etas = [row["eta_s"] for row in per_model.values() if row["pending"]]
    totals["eta_s"] = 0 if not etas else (None if any(eta is None for eta in etas) else max(etas))

    result: dict[str, Any] = {
        "utc": utc_now_iso(),
        "cells_file": str(cells_path),
        "out_dir": str(out_dir),
        "salt_present": bool(salt),
        "models": dict(sorted(per_model.items())),
        "totals": totals,
        "orphan_raw_files": len(done - set(blinds.values())) if salt else len(done),
        "active_runner_locks": store.held_locks(),
        "heartbeats": store.read_heartbeats(),
    }
    if prepare is not None and salt:
        mismatch = 0
        by_blind = {blinds[cell.cell_id]: cell for cell in cells}
        for blind in done & set(by_blind):
            cell = by_blind[blind]
            try:
                stored = json.loads(store.raw_path(blind).read_text(encoding="utf-8")).get("request_sha256")
            except (OSError, json.JSONDecodeError):
                mismatch += 1
                continue
            expected = sha256_hex(canonical_json(prepare(cell.model, cell.system, cell.messages,
                                                         cell.inference, cell.additional)))
            mismatch += stored != expected
        result["raw_request_mismatch"] = mismatch
    return result


def print_status(status: dict[str, Any]) -> None:
    header = (f"{'model':44} {'total':>7} {'done':>7} {'failed':>6} {'pending':>7} {'ok/1h':>6} "
              f"{'thr/1h':>6} {'err/1h':>6} {'lat_ms':>7} {'ETA':>8}")
    print(f"status at {status['utc']}")
    print(f"cells: {status['cells_file']}\nout:   {status['out_dir']}")
    if not status["salt_present"]:
        print("(no KEY/salt.txt yet: nothing has run in this directory)")
    print(header)
    print("-" * len(header))
    for model, row in status["models"].items():
        latency = row["mean_latency_ms_1h"] if row["mean_latency_ms_1h"] is not None else "-"
        print(f"{model:44} {row['total']:>7} {row['done']:>7} {row['failed']:>6} {row['pending']:>7} "
              f"{row['ok_1h']:>6} {row['throttled_1h']:>6} {row['other_errors_1h']:>6} {latency:>7} "
              f"{fmt_duration(row['eta_s']):>8}")
    totals = status["totals"]
    print("-" * len(header))
    print(f"{'ALL (ETA = slowest model)':44} {totals['total']:>7} {totals['done']:>7} "
          f"{totals['failed']:>6} {totals['pending']:>7} {totals['ok_1h']:>6} {totals['throttled_1h']:>6} "
          f"{totals['other_errors_1h']:>6} {'':>7} {fmt_duration(totals['eta_s']):>8}")
    if status["orphan_raw_files"]:
        print(f"note: {status['orphan_raw_files']} raw file(s) belong to cells that are not in this cells file")
    if "raw_request_mismatch" in status:
        print(f"verify: {status['raw_request_mismatch']} done cell(s) whose stored request_sha256 "
              "differs from the current cells file")
    locks = status["active_runner_locks"]
    print(f"active runners (held locks): {', '.join(locks) if locks else 'none'}")
    for beat in status["heartbeats"]:
        when = parse_utc(beat.get("utc"))
        age = (datetime.now(timezone.utc) - when).total_seconds() if when else None
        paused = beat.get("credentials_paused_since")
        print(f"heartbeat shard={beat.get('shard')} state={beat.get('state')} pid={beat.get('pid')} "
              f"age={fmt_duration(age)} exit={beat.get('exit_code', '-')}"
              f"{'  CREDENTIALS PAUSED since ' + paused if paused else ''}")
        for model, lane in (beat.get("lanes") or {}).items():
            if lane.get("disabled"):
                print(f"  DISABLED {model}: {lane['disabled']}")
            elif beat.get("state") != "exited":
                print(f"  {model}: queued={lane.get('queued')} in_flight={lane.get('in_flight')} "
                      f"limit={lane.get('limit')}")
