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
import fcntl
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
DEFAULT_CONDITIONS = ["supportive_control", "permission_gate"]
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
    core_path = PROMPTS_DIR / "shared_supportive_core_zh.txt"
    core = core_path.read_text(encoding="utf-8").strip()
    policy_names = {
        "supportive_control": "supportive_control_policy_zh.txt",
        "permission_gate": "permission_gate_policy_zh.txt",
    }
    policy_name = policy_names.get(condition)
    if not policy_name:
        raise ValueError(f"unknown condition: {condition}")
    policy_path = PROMPTS_DIR / policy_name
    policy = policy_path.read_text(encoding="utf-8").strip()
    sources = [
        str(core_path.relative_to(ROOT)),
        str(policy_path.relative_to(ROOT)),
    ]
    return core + "\n\n" + policy, sources


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


def conversation_path(run_dir: Path, spec: ConversationSpec) -> Path:
    return run_dir / f"{spec.conversation_id}.json"


def _material_descriptor(
    models: list[str],
    tracks: list[str],
    conditions: list[str],
    repeats: int,
    seed: int,
    max_turns: int | None,
    plan: list[ConversationSpec],
) -> dict[str, Any]:
    track_material = {}
    for name in tracks:
        track = load_track(name)
        track_material[name] = {
            "id": track["id"],
            "sha256": sha256_text(json.dumps(track, ensure_ascii=False, sort_keys=True)),
            "turns": len(track["turns"][:max_turns] if max_turns else track["turns"]),
        }
    prompt_material = {}
    for name in conditions:
        prompt, sources = load_prompt(name)
        prompt_material[name] = {"sources": sources, "sha256": sha256_text(prompt)}
    descriptor = {
        "schema_version": 2,
        "models": models,
        "tracks": tracks,
        "conditions": conditions,
        "repeats": repeats,
        "seed": seed,
        "max_turns": max_turns,
        "max_tokens": MAX_TOKENS,
        "tracks_material": track_material,
        "prompts_material": prompt_material,
        "plan": [asdict(spec) for spec in plan],
        "runner_sha256": sha256_text(Path(__file__).read_text(encoding="utf-8")),
    }
    descriptor["config_sha256"] = sha256_text(
        json.dumps(descriptor, ensure_ascii=False, sort_keys=True)
    )
    return descriptor


def _validate_manifest(existing: dict[str, Any], expected: dict[str, Any]) -> None:
    if existing.get("config_sha256") != expected.get("config_sha256"):
        raise RuntimeError(
            "REFUSING RESUME: experiment configuration drifted. Models, scripts, "
            "prompts, runner code, seed, repeat count, turn limit, or MAX_TOKENS changed. "
            "Start a new run ID instead of mixing experiments."
        )


def _validate_checkpoint(
    record: dict[str, Any],
    spec: ConversationSpec,
    track: dict[str, Any],
    system: str,
    user_turns: list[str],
) -> None:
    if record.get("spec") != asdict(spec):
        raise RuntimeError(f"checkpoint spec mismatch: {spec.conversation_id}")
    expected_script_hash = sha256_text(json.dumps(track, ensure_ascii=False, sort_keys=True))
    if record.get("script", {}).get("sha256") != expected_script_hash:
        raise RuntimeError(f"checkpoint script drift: {spec.conversation_id}")
    if record.get("system_prompt", {}).get("sha256") != sha256_text(system):
        raise RuntimeError(f"checkpoint system-prompt drift: {spec.conversation_id}")
    if record.get("max_tokens") != MAX_TOKENS:
        raise RuntimeError(f"checkpoint maxTokens drift: {spec.conversation_id}")
    transcript = record.get("transcript", [])
    if not isinstance(transcript, list) or len(transcript) > len(user_turns):
        raise RuntimeError(f"invalid checkpoint transcript: {spec.conversation_id}")
    for index, turn in enumerate(transcript):
        if turn.get("turn") != index + 1 or turn.get("user") != user_turns[index]:
            raise RuntimeError(f"checkpoint turn mismatch: {spec.conversation_id} turn {index + 1}")
        if not isinstance(turn.get("assistant"), str) or not turn["assistant"]:
            raise RuntimeError(f"checkpoint missing assistant text: {spec.conversation_id}")


def checkpoint_state(
    run_dir: Path,
    spec: ConversationSpec,
    max_turns: int | None,
) -> tuple[str, int]:
    path = conversation_path(run_dir, spec)
    if not path.exists():
        return "new", 0
    track = load_track(spec.track)
    system, _ = load_prompt(spec.condition)
    user_turns = track["turns"][:max_turns] if max_turns else track["turns"]
    record = read_json(path)
    _validate_checkpoint(record, spec, track, system, user_turns)
    completed_turns = len(record.get("transcript", []))
    if record.get("status") == "clean":
        if completed_turns != len(user_turns):
            raise RuntimeError(f"clean checkpoint is incomplete: {spec.conversation_id}")
        return "clean", completed_turns
    if record.get("status") != "in_progress":
        raise RuntimeError(f"unknown checkpoint status: {spec.conversation_id}")
    return "in_progress", completed_turns


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
    path = conversation_path(run_dir, spec)
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    if path.exists():
        record = read_json(path)
        _validate_checkpoint(record, spec, track, system, user_turns)
        if record.get("status") == "clean":
            log(f"[conversation {spec.number:02d}/{total}] SKIP complete={spec.conversation_id}")
            return record
        transcript = record["transcript"]
        record["resume_count"] = int(record.get("resume_count", 0)) + 1
        if record.get("pending_turn") is not None:
            record.setdefault("recovery_events", []).append(
                {
                    "at": now,
                    "event": "retry_pending_turn_after_interruption",
                    "turn": record["pending_turn"],
                }
            )
        log(
            f"[conversation {spec.number:02d}/{total}] RESUME cell={spec.cell_id} "
            f"at_turn={len(transcript) + 1}/{len(user_turns)} resume={record['resume_count']}"
        )
    else:
        transcript = []
        record = {
            "schema_version": 2,
            "spec": asdict(spec),
            "script": {
                "id": track["id"],
                "sha256": sha256_text(json.dumps(track, ensure_ascii=False, sort_keys=True)),
            },
            "system_prompt": {"sources": prompt_sources, "sha256": sha256_text(system)},
            "max_tokens": MAX_TOKENS,
            "status": "in_progress",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "resume_count": 0,
            "pending_turn": None,
            "elapsed_ms": 0,
            "recovery_events": [],
            "transcript": transcript,
        }
        atomic_json(path, record)
        log(
            f"[conversation {spec.number:02d}/{total}] START cell={spec.cell_id} "
            f"repeat={spec.repeat} turns={len(user_turns)}"
        )

    messages: list[dict[str, str]] = []
    for turn in transcript:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["assistant"]})

    session_started = time.monotonic()
    base_elapsed_ms = int(record.get("elapsed_ms", 0))
    for turn_number in range(len(transcript) + 1, len(user_turns) + 1):
        user_text = user_turns[turn_number - 1]
        messages.append({"role": "user", "content": user_text})
        record["pending_turn"] = turn_number
        record["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        record["elapsed_ms"] = base_elapsed_ms + round((time.monotonic() - session_started) * 1000)
        atomic_json(path, record)

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
        record["pending_turn"] = None
        record["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        record["elapsed_ms"] = base_elapsed_ms + round((time.monotonic() - session_started) * 1000)
        atomic_json(path, record)
        log(
            f"[conversation {spec.number:02d}/{total}] turn={turn_number}/{len(user_turns)} "
            f"model={spec.model} latency={result.get('gatewayLatencyMs')}ms CHECKPOINT"
        )

    record["status"] = "clean"
    record["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    record["updated_at"] = record["completed_at"]
    record["pending_turn"] = None
    record["elapsed_ms"] = base_elapsed_ms + round((time.monotonic() - session_started) * 1000)
    atomic_json(path, record)
    log(
        f"[conversation {spec.number:02d}/{total}] DONE cell={spec.cell_id} "
        f"repeat={spec.repeat} elapsed={record['elapsed_ms']}ms"
    )
    return record


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def acquire_run_lock(run_dir: Path):
    lock_path = run_dir / ".run.lock"
    handle = lock_path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        handle.close()
        raise RuntimeError(
            f"run is already active in another process: {run_dir.name}"
        ) from error
    handle.seek(0)
    handle.truncate()
    handle.write(f"pid={os.getpid()} started={dt.datetime.now(dt.timezone.utc).isoformat()}\n")
    handle.flush()
    return handle


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
    parser.add_argument(
        "--status-json",
        action="store_true",
        help="print resumable run status without starting or contacting a gateway",
    )
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
    if not args.status_json:
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

    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = OUT_ROOT / run_id
    if args.status_json:
        if not run_dir.exists() or not (run_dir / "manifest.json").exists():
            print(json.dumps({"run_id": run_id, "exists": False, "completed": 0, "requests_done": 0, "requests_remaining": expected_requests}))
            return 0
        expected_material = _material_descriptor(
            models, tracks, conditions, args.repeats, args.seed, args.max_turns, plan
        )
        _validate_manifest(read_json(run_dir / "manifest.json"), expected_material)
        completed = 0
        requests_done = 0
        in_progress = 0
        for spec in plan:
            state, turns_done = checkpoint_state(run_dir, spec, args.max_turns)
            requests_done += turns_done
            if state == "clean":
                completed += 1
            elif state == "in_progress":
                in_progress += 1
        print(json.dumps({
            "run_id": run_id,
            "exists": True,
            "completed": completed,
            "in_progress": in_progress,
            "expected_conversations": len(plan),
            "requests_done": requests_done,
            "requests_remaining": expected_requests - requests_done,
            "complete": completed == len(plan),
        }))
        return 0

    if not args.gateway_url or not args.gateway_token:
        raise SystemExit("LOCAL_MODEL_GATEWAY_URL and LOCAL_MODEL_GATEWAY_TOKEN are required")
    manifest_path = run_dir / "manifest.json"
    expected_material = _material_descriptor(
        models, tracks, conditions, args.repeats, args.seed, args.max_turns, plan
    )
    is_resume = run_dir.exists()
    if is_resume:
        if not manifest_path.exists():
            raise RuntimeError(
                f"REFUSING RESUME: {run_dir} exists without manifest.json"
            )
        existing_manifest = read_json(manifest_path)
        _validate_manifest(existing_manifest, expected_material)
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        manifest = {
            **expected_material,
            "run_id": run_id,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "repository_revision": git_revision(),
        }
        atomic_json(manifest_path, manifest)

    run_lock = acquire_run_lock(run_dir)
    # Keep a credential-free, copyable recovery command with the artifacts.
    resume_config = (
        f"PILOT_RUN_ID={run_id} "
        f"PILOT_MODELS={','.join(models)} "
        f"PILOT_TRACKS={','.join(tracks)} "
        f"PILOT_CONDITIONS={','.join(conditions)} "
        f"PILOT_REPEATS={args.repeats} "
        f"PILOT_MAX_WORKERS={args.max_workers} "
        f"PILOT_MAX_TURNS={turns_per_conversation} "
        "/home/alexjia/.workspace/local-model-gateway/run_permission_gate_pilot.sh"
    )
    (run_dir / "RESUME_COMMAND.txt").write_text(resume_config + "\n", encoding="utf-8")

    client = GatewayClient(args.gateway_url, args.gateway_token)
    client.health()

    completed_before: list[ConversationSpec] = []
    pending: list[ConversationSpec] = []
    requests_already_done = 0
    for spec in plan:
        state, completed_turns = checkpoint_state(run_dir, spec, args.max_turns)
        requests_already_done += completed_turns
        if state == "clean":
            completed_before.append(spec)
        else:
            pending.append(spec)
    remaining_requests = expected_requests - requests_already_done
    mode = "RESUME" if is_resume else "NEW"
    print(
        f"{mode} run_id={run_id} complete_before={len(completed_before)}/{len(plan)} "
        f"pending={len(pending)} requests_done={requests_already_done}/{expected_requests} "
        f"requests_remaining={remaining_requests}",
        flush=True,
    )
    resume_env = " ".join(
        [
            f"PILOT_RUN_ID={run_id}",
            f"PILOT_MODELS={','.join(models)}",
            f"PILOT_TRACKS={','.join(tracks)}",
            f"PILOT_CONDITIONS={','.join(conditions)}",
            f"PILOT_REPEATS={args.repeats}",
            f"PILOT_MAX_WORKERS={args.max_workers}",
            f"PILOT_MAX_TURNS={turns_per_conversation}",
        ]
    )
    print(
        f"RESUME CONFIG: {resume_env}",
        flush=True,
    )

    errors: list[dict[str, Any]] = []
    if pending:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
            futures = {
                pool.submit(run_conversation, spec, len(plan), run_dir, client, args.max_turns): spec
                for spec in pending
            }
            for future in concurrent.futures.as_completed(futures):
                spec = futures[future]
                try:
                    future.result()
                    error_path = run_dir / f"{spec.conversation_id}__ERROR.json"
                    if error_path.exists():
                        error_path.unlink()
                except Exception as error:
                    item = {
                        "spec": asdict(spec),
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    }
                    errors.append(item)
                    atomic_json(run_dir / f"{spec.conversation_id}__ERROR.json", item)
                    log(
                        f"[conversation {spec.number:02d}/{len(plan)}] ERROR "
                        f"{type(error).__name__}: {error}"
                    )

    clean_records = []
    in_progress = []
    for spec in plan:
        path = conversation_path(run_dir, spec)
        if not path.exists():
            continue
        record = read_json(path)
        if record.get("status") == "clean":
            clean_records.append(record)
        else:
            in_progress.append(
                {
                    "conversation_id": spec.conversation_id,
                    "completed_turns": len(record.get("transcript", [])),
                    "pending_turn": record.get("pending_turn"),
                }
            )

    summary = {
        "run_id": run_id,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "clean_conversations": len(clean_records),
        "in_progress_conversations": in_progress,
        "error_conversations_this_attempt": len(errors),
        "expected_conversations": len(plan),
        "complete": len(clean_records) == len(plan),
        "errors_this_attempt": errors,
    }
    atomic_json(run_dir / "summary.json", summary)
    print(
        f"RUN DONE clean={len(clean_records)}/{len(plan)} "
        f"in_progress={len(in_progress)} errors_this_attempt={len(errors)} "
        f"output={run_dir.relative_to(ROOT)}",
        flush=True,
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
