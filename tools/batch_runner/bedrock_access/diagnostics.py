"""probe and ramp: small real Bedrock calls.

probe  checks the request format (system prompt + user/assistant/user) per
       model, which sampling parameters are accepted, how reasoning / effort /
       extended thinking can be set via additionalModelRequestFields, and
       whether thinking is on by default. Verbatim service errors are kept.
       Prompts are canned test strings, so short reply text is stored.
ramp   short realistic calls (Chinese, ~300 output tokens) at increasing
       concurrency per model. Stores metadata only (no text).

Not part of the runner's code hash: nothing here writes experiment data.
"""

from __future__ import annotations

import collections
import dataclasses
import json
import logging
import random
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backend import AccessError, BedrockConverseBackend
from .credentials import caller_identity
from .errors import THROTTLED, TRANSIENT
from .models import is_anthropic, is_openai

LOG = logging.getLogger("bedrock_access")

PROBE_SYSTEM = "You are a terse assistant. End every reply with the exact marker [SYS-OK]."
PROBE_TURNS = (
    ("user", "Remember this code word: PELICAN. Reply only with: Stored."),
    ("assistant", "Stored."),
    ("user", "What was the code word? Reply with just the word."),
)
REASONING_TURNS = (
    ("user", "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. "
             "How much does the ball cost? Also, how many prime numbers are smaller than 60? "
             "Give both answers in one short line."),
)
SMALL = {"maxTokens": 60}
ROOM = {"maxTokens": 2000}
EFFORT_LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
CLAUDE_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
GPT_EFFORT_FORMS: dict[str, Any] = {
    "reasoning_effort": lambda level: {"reasoning_effort": level},
    "reasoning.effort": lambda level: {"reasoning": {"effort": level}},
    "reasoningEffort": lambda level: {"reasoningEffort": level},
    "effort": lambda level: {"effort": level},
    "reasoning_config.effort": lambda level: {"reasoning_config": {"effort": level}},
    "output_config.effort": lambda level: {"output_config": {"effort": level}},
}

RAMP_SYSTEM = "你是一位耐心、友善的中文助手。"
RAMP_USER = "我最近工作压力很大，晚上经常睡不好。你能给我一些具体的建议吗？请用中文回答，大约两百字。"


@dataclasses.dataclass
class Variant:
    name: str
    group: str
    system: bool
    turns: tuple[tuple[str, str], ...]
    inference: dict[str, Any]
    additional: dict[str, Any] | None = None
    purpose: str = ""


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _call(backend: BedrockConverseBackend, model: str, variant: Variant, max_retries: int = 6) -> dict[str, Any]:
    request = backend.prepare(model, PROBE_SYSTEM if variant.system else None, variant.turns,
                              variant.inference, variant.additional)
    result: dict[str, Any] = {
        "model": model,
        "variant": variant.name,
        "group": variant.group,
        "purpose": variant.purpose,
        "request": {
            "system_prompt": variant.system,
            "turn_roles": [role for role, _ in variant.turns],
            "inferenceConfig": request["inferenceConfig"],
            "additionalModelRequestFields": request.get("additionalModelRequestFields"),
        },
        "retries": 0,
    }
    for attempt in range(1, max_retries + 2):
        started = time.monotonic()
        try:
            reply = backend.invoke(model, request)
        except AccessError as error:
            result["latency_ms"] = round((time.monotonic() - started) * 1000)
            if error.kind in (THROTTLED, TRANSIENT) and attempt <= max_retries:
                result["retries"] += 1
                time.sleep(min(60.0, 2.0 * 2 ** (attempt - 1)) * (0.5 + random.random() / 2))
                continue
            result.update(accepted=False, error_kind=error.kind, error_code=error.code,
                          http_status=error.http_status, error_message=error.message)
            return result
        text = reply.text
        result.update(
            accepted=True,
            latency_ms=round((time.monotonic() - started) * 1000),
            stop_reason=reply.stop_reason,
            usage=reply.usage,
            block_types=reply.block_types,
            reasoning_blocks=len(reply.reasoning),
            reasoning_chars=sum(len(r) for r in reply.reasoning),
            reasoning_preview=(reply.reasoning[0][:160] if reply.reasoning else None),
            redacted_reasoning_blocks=reply.redacted_reasoning_blocks,
            text=text[:400],
        )
        if variant.turns == PROBE_TURNS:
            result["checks"] = {
                "remembered_turn_1": "pelican" in text.lower(),
                "system_marker": "sys-ok" in text.lower(),  # may be cut short by maxTokens
                "truncated": reply.stop_reason == "max_tokens",
            }
        return result
    raise AssertionError("unreachable")


def _probe_model(backend: BedrockConverseBackend, model: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def run(variant: Variant) -> dict[str, Any]:
        outcome = _call(backend, model, variant)
        results.append(outcome)
        LOG.info("probe %-44s %-38s %s", model, variant.name,
                 "ok" if outcome["accepted"] else f"REJECTED {outcome.get('error_code')}: "
                 f"{(outcome.get('error_message') or '')[:120]}")
        return outcome

    base = [
        Variant("base", "format", True, PROBE_TURNS, SMALL, None, "system prompt + user/assistant/user"),
        Variant("no_system", "format", False, PROBE_TURNS, SMALL, None, "same turns, no system prompt (control)"),
        Variant("temperature=0.7", "sampling", True, PROBE_TURNS, {**SMALL, "temperature": 0.7}),
        Variant("temperature=1.0", "sampling", True, PROBE_TURNS, {**SMALL, "temperature": 1.0}),
        Variant("temperature=0", "sampling", True, PROBE_TURNS, {**SMALL, "temperature": 0}),
        Variant("topP=0.9", "sampling", True, PROBE_TURNS, {**SMALL, "topP": 0.9}),
        Variant("temperature=0.7+topP=0.9", "sampling", True, PROBE_TURNS,
                {**SMALL, "temperature": 0.7, "topP": 0.9}),
        Variant("unknown_additional_field", "additional", True, PROBE_TURNS, SMALL,
                {"zz_probe_unknown_field": 1}, "are unknown additionalModelRequestFields rejected or ignored?"),
        Variant("default@2000", "reasoning", False, REASONING_TURNS, ROOM, None,
                "no reasoning settings: are reasoning blocks returned by default?"),
    ]
    for variant in base:
        run(variant)

    if is_openai(model):
        accepted_forms: list[tuple[str, bool]] = []
        for form, make in GPT_EFFORT_FORMS.items():
            low = run(Variant(f"{form}=low", "effort", True, PROBE_TURNS, SMALL, make("low")))
            bogus = run(Variant(f"{form}=bogus-level", "effort", True, PROBE_TURNS, SMALL, make("bogus-level"),
                                "an invalid value: rejected means the field is actually parsed"))
            if low["accepted"]:
                accepted_forms.append((form, not bogus["accepted"]))
        run(Variant("reasoningConfig(nova-style)", "effort", True, PROBE_TURNS, SMALL,
                    {"reasoningConfig": {"type": "enabled", "maxReasoningEffort": "low"}}))
        # sweep levels for up to two accepted forms, validated (bogus rejected) forms first
        accepted_forms.sort(key=lambda item: not item[1])
        for form, _validated in accepted_forms[:2]:
            for level in EFFORT_LEVELS:
                run(Variant(f"{form}={level}@2000", "effort_sweep", False, REASONING_TURNS, ROOM,
                            GPT_EFFORT_FORMS[form](level), "effect of the level on output tokens"))
    if is_anthropic(model):
        claude = [
            Variant("thinking.disabled", "thinking", True, PROBE_TURNS, SMALL, {"thinking": {"type": "disabled"}}),
            Variant("thinking.disabled@2000", "thinking", False, REASONING_TURNS, ROOM,
                    {"thinking": {"type": "disabled"}}),
            Variant("thinking.adaptive@2000", "thinking", False, REASONING_TURNS, ROOM,
                    {"thinking": {"type": "adaptive"}}),
            Variant("thinking.adaptive+display=summarized@2000", "thinking", False, REASONING_TURNS, ROOM,
                    {"thinking": {"type": "adaptive", "display": "summarized"}}),
            Variant("thinking.enabled.budget_tokens=1024@2000", "thinking", False, REASONING_TURNS, ROOM,
                    {"thinking": {"type": "enabled", "budget_tokens": 1024}}),
            *[Variant(f"output_config.effort={level}@2000", "effort", False, REASONING_TURNS, ROOM,
                      {"output_config": {"effort": level}}) for level in CLAUDE_EFFORT_LEVELS],
            Variant("thinking.adaptive+effort=low@2000", "effort", False, REASONING_TURNS, ROOM,
                    {"thinking": {"type": "adaptive"}, "output_config": {"effort": "low"}}),
            Variant("thinking.disabled+effort=low@2000", "effort", False, REASONING_TURNS, ROOM,
                    {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}),
            Variant("thinking.disabled+effort=max@2000", "effort", False, REASONING_TURNS, ROOM,
                    {"thinking": {"type": "disabled"}, "output_config": {"effort": "max"}}),
            Variant("output_config.effort=low+anthropic_beta@2000", "effort", False, REASONING_TURNS, ROOM,
                    {"output_config": {"effort": "low"}, "anthropic_beta": ["effort-2025-11-24"]}),
            Variant("reasoning_effort=low(openai-style)", "effort", True, PROBE_TURNS, SMALL,
                    {"reasoning_effort": "low"}),
        ]
        for variant in claude:
            run(variant)
    return results


def _cell(result: dict[str, Any]) -> str:
    if result["accepted"]:
        return "accepted"
    return f"REJECTED ({result.get('error_code')})"


def _md_escape(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _probe_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Bedrock Converse probe {report['utc']}", "",
             f"identity: {report['identity']}  botocore {report['versions']['botocore_version']}", ""]
    by_model: dict[str, dict[str, dict[str, Any]]] = collections.defaultdict(dict)
    for result in report["results"]:
        by_model[result["model"]][result["variant"]] = result

    lines += ["## Summary", "",
              "| model | system+multi-turn | temperature | topP | temperature+topP | unknown extra field | "
              "reasoning blocks by default (out tokens @2000) |",
              "|---|---|---|---|---|---|---|"]
    for model, variants in by_model.items():
        base = variants.get("base", {})
        checks = base.get("checks", {})
        fmt = (f"ok (remembered={checks.get('remembered_turn_1')}, system obeyed={checks.get('system_marker')})"
               if base.get("accepted") else _cell(base))
        default = variants.get("default@2000", {})
        default_desc = (f"{default.get('reasoning_blocks', 0)} text + {default.get('redacted_reasoning_blocks', 0)} redacted "
                        f"({(default.get('usage') or {}).get('outputTokens')})" if default.get("accepted") else _cell(default))
        lines.append(f"| {model} | {fmt} | {_cell(variants['temperature=0.7'])} | {_cell(variants['topP=0.9'])} | "
                     f"{_cell(variants['temperature=0.7+topP=0.9'])} | {_cell(variants['unknown_additional_field'])} | "
                     f"{default_desc} |")
    lines.append("")

    for model, variants in by_model.items():
        lines += [f"## {model}", "",
                  "| variant | result | stop | in/out tokens | reasoning blocks (chars) | latency ms | text / verbatim error |",
                  "|---|---|---|---|---|---|---|"]
        for name, result in variants.items():
            usage = result.get("usage") or {}
            if result["accepted"]:
                detail = _md_escape(result.get("text", ""))[:160]
                if result.get("checks"):
                    detail += f" {result['checks']}"
                if result.get("reasoning_preview"):
                    detail += f" [reasoning: {_md_escape(result['reasoning_preview'])[:80]}]"
            else:
                detail = f"{result.get('error_kind')} {result.get('http_status')}: {_md_escape(result.get('error_message'))}"
            reasoning = (f"{result.get('reasoning_blocks', 0)} ({result.get('reasoning_chars', 0)})"
                         f"{' +' + str(result['redacted_reasoning_blocks']) + ' redacted' if result.get('redacted_reasoning_blocks') else ''}"
                         if result["accepted"] else "")
            lines.append(f"| {name} | {_cell(result)} | {result.get('stop_reason', '')} | "
                         f"{usage.get('inputTokens', '')}/{usage.get('outputTokens', '')} | {reasoning} | "
                         f"{result.get('latency_ms', '')} | {detail} |")
        lines.append("")
    return "\n".join(lines)


def cmd_probe(args: Any, backend: BedrockConverseBackend) -> int:
    models = sorted(set(args.models.split(",")) if args.models else backend.models())
    out = Path(args.out) / "probe"
    out.mkdir(parents=True, exist_ok=True)
    identity = caller_identity(backend.token_source) if backend.token_source is not None else {}
    LOG.info("probe identity=%s models=%d", identity, len(models))
    results: list[dict[str, Any]] = []
    lock = threading.Lock()

    def worker(model: str) -> None:
        rows = _probe_model(backend, model)
        with lock:
            results.extend(rows)

    threads = [threading.Thread(target=worker, args=(model,), daemon=True) for model in models]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    order = {model: index for index, model in enumerate(models)}
    results.sort(key=lambda r: order[r["model"]])
    report = {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "identity": identity,
              "versions": backend.versions(), "results": results}
    stamp = _stamp()
    (out / f"probe-{stamp}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    markdown = _probe_markdown(report)
    (out / f"probe-{stamp}.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    LOG.info("probe written to %s", out / f"probe-{stamp}.json")
    return 0


# --------------------------------------------------------------------------- ramp


def _ramp_model(backend: BedrockConverseBackend, model: str, steps: list[int], calls_per_step: int,
                max_tokens: int, additional: dict[str, Any] | None, pause_s: float) -> list[dict[str, Any]]:
    request = backend.prepare(model, RAMP_SYSTEM, (("user", RAMP_USER),), {"maxTokens": max_tokens}, additional)
    rows = []

    def one(_index: int) -> dict[str, Any]:
        started = time.monotonic()
        try:
            reply = backend.invoke(model, request)
        except AccessError as error:
            return {"status": error.kind, "code": error.code, "latency_ms": round((time.monotonic() - started) * 1000),
                    "message": None if error.kind == THROTTLED else error.message[:200]}
        return {"status": "ok", "latency_ms": round((time.monotonic() - started) * 1000),
                "in_tokens": reply.usage.get("inputTokens"), "out_tokens": reply.usage.get("outputTokens"),
                "stop_reason": reply.stop_reason, "text_chars": len(reply.text),
                "reasoning_blocks": len(reply.reasoning)}

    for concurrency in steps:
        calls = max(calls_per_step, concurrency)
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            calls_out = list(pool.map(one, range(calls)))
        wall = time.monotonic() - started
        ok = [c for c in calls_out if c["status"] == "ok"]
        latencies = [c["latency_ms"] for c in ok]
        out_tokens = [c["out_tokens"] for c in ok if isinstance(c.get("out_tokens"), (int, float))]
        errors = collections.Counter(f"{c['status']}:{c.get('code')}" for c in calls_out
                                     if c["status"] not in ("ok", THROTTLED))
        row = {
            "model": model,
            "concurrency": concurrency,
            "calls": calls,
            "ok": len(ok),
            "throttled": sum(c["status"] == THROTTLED for c in calls_out),
            "other_errors": dict(errors),
            "error_examples": sorted({c["message"] for c in calls_out if c.get("message")})[:3],
            "wall_s": round(wall, 1),
            "ok_calls_per_min": round(len(ok) / wall * 60, 1) if wall else None,
            "mean_latency_ms": round(statistics.mean(latencies)) if latencies else None,
            "p50_latency_ms": round(statistics.median(latencies)) if latencies else None,
            "max_latency_ms": max(latencies) if latencies else None,
            "mean_out_tokens": round(statistics.mean(out_tokens)) if out_tokens else None,
            "out_tokens_per_s": round(sum(out_tokens) / wall, 1) if wall and out_tokens else None,
            "stop_reasons": dict(collections.Counter(c.get("stop_reason") for c in ok)),
            "empty_text": sum(1 for c in ok if not c.get("text_chars")),
            "per_call": calls_out,
        }
        rows.append(row)
        LOG.info("ramp %-44s c=%-2d ok=%d/%d thr=%d err=%s calls/min=%s mean_lat=%sms out_tok=%s",
                 model, concurrency, row["ok"], calls, row["throttled"], dict(errors) or 0,
                 row["ok_calls_per_min"], row["mean_latency_ms"], row["mean_out_tokens"])
        time.sleep(pause_s)
    return rows


def _ramp_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Bedrock Converse concurrency ramp {report['utc']}", "",
             f"request: system + one Chinese user message, maxTokens={report['max_tokens']}, "
             f"calls per step = max({report['calls_per_step']}, concurrency), no retries; "
             f"models ramped {'one at a time' if report['sequential'] else 'in parallel'}.",
             f"additional fields: GPT={report['gpt_additional']} Claude={report['claude_additional']}", "",
             "| model | conc | ok/calls | throttled | other errors | wall s | ok calls/min | mean lat ms | "
             "p50 | max | mean out tok | out tok/s | stop reasons |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in report["rows"]:
        lines.append(
            f"| {row['model']} | {row['concurrency']} | {row['ok']}/{row['calls']} | {row['throttled']} | "
            f"{row['other_errors'] or ''} | {row['wall_s']} | {row['ok_calls_per_min']} | {row['mean_latency_ms']} | "
            f"{row['p50_latency_ms']} | {row['max_latency_ms']} | {row['mean_out_tokens']} | {row['out_tokens_per_s']} | "
            f"{row['stop_reasons']} |")
    return "\n".join(lines) + "\n"


def cmd_ramp(args: Any, backend: BedrockConverseBackend) -> int:
    models = sorted(set(args.models.split(",")) if args.models else backend.models())
    steps = [int(step) for step in args.steps.split(",") if step.strip()]
    gpt_additional = json.loads(args.gpt_additional) if args.gpt_additional else None
    claude_additional = json.loads(args.claude_additional) if args.claude_additional else None
    out = Path(args.out) / "ramp"
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    lock = threading.Lock()

    def worker(model: str) -> None:
        additional = gpt_additional if is_openai(model) else claude_additional if is_anthropic(model) else None
        result = _ramp_model(backend, model, steps, args.calls_per_step, args.max_tokens, additional, pause_s=5.0)
        with lock:
            rows.extend(result)

    if args.sequential:
        for model in models:
            worker(model)
    else:
        threads = [threading.Thread(target=worker, args=(model,), daemon=True) for model in models]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    order = {model: index for index, model in enumerate(models)}
    rows.sort(key=lambda r: (order[r["model"]], r["concurrency"]))
    report = {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "versions": backend.versions(),
              "steps": steps, "calls_per_step": args.calls_per_step, "max_tokens": args.max_tokens,
              "sequential": bool(args.sequential), "gpt_additional": gpt_additional,
              "claude_additional": claude_additional, "rows": rows}
    stamp = _stamp()
    (out / f"ramp-{stamp}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    markdown = _ramp_markdown(report)
    (out / f"ramp-{stamp}.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    LOG.info("ramp written to %s", out / f"ramp-{stamp}.json")
    return 0

