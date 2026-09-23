#!/usr/bin/env python3
"""Run the synthetic permission-gate pilot through a local model gateway.

The runner knows only a loopback URL and per-process local token. Cloud auth,
provider clients, and credential refresh remain outside this repository.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PILOT_DIR = ROOT / "matrix-pilot"
SCRIPTS_DIR = PILOT_DIR / "scripts"
PROMPTS_DIR = PILOT_DIR / "prompts"
OUT_ROOT = ROOT / "model-comparison" / "permission-gate-pilot"

DEFAULT_MODELS = [
    "us.anthropic.claude-sonnet-5",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.openai.gpt-5.6-sol",
]
DEFAULT_TRACKS = ["verdict", "bias"]
DEFAULT_CONDITIONS = ["supportive", "permission_gate"]
DEFAULT_REPEATS = 5
DEFAULT_SEED = 20260923
MAX_TOKENS = 4000

_print_lock = threading.Lock()


def log(message: str) -> None:
    with _print_lock:
        print(message, flush=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--short=12", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_track(name: str) -> dict[str, Any]:
    path = SCRIPTS_DIR / f"S2_{name}.json"
    if not path.exists():
        raise ValueError(f"unknown track: {name}")
    track = read_json(path)
    turns = track.get("turns")
    if not isinstance(turns, list) or not turns or not all(isinstance(x, str) and x for x in turns):
        raise ValueError(f"invalid turns in {path}")
    return track


def load_prompt(condition: str) -> tuple[str, list[str]]:
    baseline_path = PROMPTS_DIR / "commercial_style_supportive_zh.txt"
    baseline = baseline_path.read_text(encoding="utf-8").strip()
    sources = [str(baseline_path.relative_to(ROOT))]
    if condition == "supportive":
        return baseline, sources
    if condition == "permission_gate":
        addon_path = PROMPTS_DIR / "permission_gate_addon_zh.txt"
        addon = addon_path.read_text(encoding="utf-8").strip()
        sources.append(str(addon_path.relative_to(ROOT)))
        return baseline + "\n\n" + addon, sources
    raise ValueError(f"unknown condition: {condition}")


@dataclass(frozen=True)
class ConversationSpec:
    number: int
    cell_id: str
    conversation_id: str
    model: str
    track: str
    condition: str
    repeat: int


def build_plan(
    models: list[str],
    tracks: list[str],
    conditions: list[str],
    repeats: int,
    seed: int,
) -> list[ConversationSpec]:
    raw: list[tuple[str, str, str, int]] = []
    for model in models:
        for track in tracks:
            for condition in conditions:
                for repeat in range(1, repeats + 1):
                    raw.append((model, track, condition, repeat))
    random.Random(seed).shuffle(raw)
    plan = []
    for number, (model, track, condition, repeat) in enumerate(raw, 1):
        short = model.replace("us.anthropic.", "").replace("us.openai.", "")
        cell_id = f"{short}__{track}__{condition}"
        plan.append(
            ConversationSpec(
                number=number,
                cell_id=cell_id,
                conversation_id=f"{cell_id}__r{repeat:02d}",
                model=model,
                track=track,
                condition=condition,
                repeat=repeat,
            )
        )
    return plan


class GatewayClient:
    def __init__(self, url: str, token: str, timeout: int = 210):
        if not url.startswith("http://127.0.0.1:"):
            raise ValueError("gateway URL must be loopback http://127.0.0.1:<port>")
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def health(self) -> None:
        with urllib.request.urlopen(self.url + "/healthz", timeout=5) as response:
            body = json.load(response)
        if body.get("status") != "ok":
            raise RuntimeError("gateway health check failed")

    def converse(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, str]],
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "system": system,
            "messages": messages,
            "inferenceConfig": {"maxTokens": MAX_TOKENS},
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            request = urllib.request.Request(
                self.url + "/v1/converse",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-Gateway-Token": self.token,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    result = json.load(response)
                text = extract_text(result)
                if result.get("stopReason") == "max_tokens":
                    raise RuntimeError(f"response truncated at maxTokens={MAX_TOKENS}")
                if not text:
                    raise RuntimeError("empty text response")
                result["text"] = text
                return result
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code not in {429, 502, 503, 504} or attempt == max_attempts:
                    raise RuntimeError(f"gateway returned HTTP {error.code}") from error
            except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
                last_error = error
                if attempt == max_attempts:
                    raise
            time.sleep(2 ** (attempt - 1))
        raise RuntimeError("gateway request failed") from last_error


def extract_text(result: dict[str, Any]) -> str:
    blocks = result.get("output", {}).get("message", {}).get("content", [])
    return "".join(block.get("text", "") for block in blocks if isinstance(block, dict)).strip()


def atomic_json(path: Path, value: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def run_conversation(
    spec: ConversationSpec,
    total: int,
    run_dir: Path,
    client: GatewayClient,
    max_turns: int | None,
) -> dict[str, Any]:
    track = load_track(spec.track)
    system, prompt_sources = load_prompt(spec.condition)
    user_turns = track["turns"][:max_turns] if max_turns else track["turns"]
    log(
        f"[conversation {spec.number:02d}/{total}] START cell={spec.cell_id} "
        f"repeat={spec.repeat} turns={len(user_turns)}"
    )
    messages: list[dict[str, str]] = []
    transcript = []
    started = time.monotonic()
    for turn_number, user_text in enumerate(user_turns, 1):
        messages.append({"role": "user", "content": user_text})
        result = client.converse(model=spec.model, system=system, messages=messages)
        assistant_text = result.pop("text")
        messages.append({"role": "assistant", "content": assistant_text})
        transcript.append(
            {
                "turn": turn_number,
                "user": user_text,
                "assistant": assistant_text,
                "model": result.get("model"),
                "region": result.get("region"),
                "stop_reason": result.get("stopReason"),
                "usage": result.get("usage", {}),
                "gateway_latency_ms": result.get("gatewayLatencyMs"),
                "request_sha256": result.get("requestSha256"),
            }
        )
        log(
            f"[conversation {spec.number:02d}/{total}] turn={turn_number}/{len(user_turns)} "
            f"model={spec.model} latency={result.get('gatewayLatencyMs')}ms"
        )
    elapsed_ms = round((time.monotonic() - started) * 1000)
    record = {
        "schema_version": 1,
        "spec": asdict(spec),
        "script": {"id": track["id"], "sha256": sha256_text(json.dumps(track, ensure_ascii=False, sort_keys=True))},
        "system_prompt": {"sources": prompt_sources, "sha256": sha256_text(system)},
        "max_tokens": MAX_TOKENS,
        "elapsed_ms": elapsed_ms,
        "status": "clean",
        "transcript": transcript,
    }
    atomic_json(run_dir / f"{spec.conversation_id}.json", record)
    log(
        f"[conversation {spec.number:02d}/{total}] DONE cell={spec.cell_id} "
        f"repeat={spec.repeat} elapsed={elapsed_ms}ms"
    )
    return record


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the permission-gate pilot")
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--tracks", default=",".join(DEFAULT_TRACKS))
    parser.add_argument("--conditions", default=",".join(DEFAULT_CONDITIONS))
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--max-turns", type=int, default=None, help="test-only truncation")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--gateway-url", default=os.environ.get("LOCAL_MODEL_GATEWAY_URL"))
    parser.add_argument("--gateway-token", default=os.environ.get("LOCAL_MODEL_GATEWAY_TOKEN"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repeats < 1 or not (1 <= args.max_workers <= 8):
        raise SystemExit("repeats must be positive and max-workers must be 1-8")
    models = parse_csv(args.models)
    tracks = parse_csv(args.tracks)
    conditions = parse_csv(args.conditions)
    for track in tracks:
        load_track(track)
    for condition in conditions:
        load_prompt(condition)
    plan = build_plan(models, tracks, conditions, args.repeats, args.seed)
    turns_per_conversation = args.max_turns or len(load_track(tracks[0])["turns"])
    expected_requests = len(plan) * turns_per_conversation
    print(
        f"PLAN conversations={len(plan)} requests={expected_requests} "
        f"models={len(models)} tracks={len(tracks)} conditions={len(conditions)} "
        f"repeats={args.repeats} seed={args.seed}",
        flush=True,
    )
    if args.plan_only:
        for spec in plan:
            print(f"  {spec.number:02d}. {spec.conversation_id}")
        return 0
    if not args.gateway_url or not args.gateway_token:
        raise SystemExit("LOCAL_MODEL_GATEWAY_URL and LOCAL_MODEL_GATEWAY_TOKEN are required")

    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = OUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    client = GatewayClient(args.gateway_url, args.gateway_token)
    client.health()

    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repository_revision": git_revision(),
        "seed": args.seed,
        "models": models,
        "tracks": tracks,
        "conditions": conditions,
        "repeats": args.repeats,
        "max_workers": args.max_workers,
        "max_turns": args.max_turns,
        "expected_conversations": len(plan),
        "expected_requests": expected_requests,
        "plan": [asdict(spec) for spec in plan],
    }
    atomic_json(run_dir / "manifest.json", manifest)

    clean: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = {
            pool.submit(run_conversation, spec, len(plan), run_dir, client, args.max_turns): spec
            for spec in plan
        }
        for future in concurrent.futures.as_completed(futures):
            spec = futures[future]
            try:
                clean.append(future.result())
            except Exception as error:
                item = {"spec": asdict(spec), "error_type": type(error).__name__, "error": str(error)}
                errors.append(item)
                atomic_json(run_dir / f"{spec.conversation_id}__ERROR.json", item)
                log(f"[conversation {spec.number:02d}/{len(plan)}] ERROR {type(error).__name__}: {error}")

    summary = {
        "run_id": run_id,
        "clean_conversations": len(clean),
        "error_conversations": len(errors),
        "expected_conversations": len(plan),
        "complete": len(clean) == len(plan),
        "errors": errors,
    }
    atomic_json(run_dir / "summary.json", summary)
    print(
        f"RUN DONE clean={len(clean)}/{len(plan)} errors={len(errors)} "
        f"output={run_dir.relative_to(ROOT)}",
        flush=True,
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
