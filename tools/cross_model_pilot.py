#!/usr/bin/env python3
"""Cross-model frozen-script replay — the paper-2 pilot matrix.

Replays a frozen user script (the same 8 scripted turns, first branch wins)
against the SAME condition prompts on several model platforms in parallel.
This is paper 2's pilot data (vendor collusion baselines / stacking design),
NOT part of the Phase-A instrument: app.py stays Bedrock+Claude only, and
the v1-freeze gate still runs through tools/frozen_pilot.py.

Artifact naming (one json + one md per cell, self-describing):

    {script}__{model-short}__{lang}__{condition}__{run-stamp}.json/.md

e.g.  S2_self_critical__gemini-3.6-flash__zh__supportive__2026-08-05T10-30-00.md

plus one RUN index per invocation:

    RUN__{script}__{lang}__{run-stamp}.md   (matrix table + signal screen)

All cells of one invocation share the run-stamp, so a run's files sort
together and a cell is traceable to its exact prompt state: each artifact
embeds the git rev of conditions/ at run time, the model id, backend,
MAX_TOKENS, and the resolved user turns.

Usage:
    python tools/cross_model_pilot.py                      # S2 x 3 models x 3 conditions, zh
    python tools/cross_model_pilot.py --script S3 --lang en
    python tools/cross_model_pilot.py --models us.anthropic.claude-sonnet-5,gemini-3.6-flash
    python tools/cross_model_pilot.py --conditions supportive,challenging
"""

from __future__ import annotations  # session laptop venv is 3.9

import argparse
import datetime
import json
import subprocess
import sys
import threading
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT))

import model_compare as mc          # backends, key loading, signal screen
from frozen_pilot import parse_script

OUT_DIR = ROOT / "model-comparison"
SCRIPTS_DIR = ROOT / "frozen-scripts"

DEFAULT_MODELS = [
    "us.anthropic.claude-sonnet-5",
    "gpt-5.6-terra",
    "gemini-3.6-flash",
]
CONDITIONS = ["supportive", "challenging", "neutral"]

_print_lock = threading.Lock()


def log(msg: str):
    with _print_lock:
        print(msg, flush=True)


def model_short(model_id: str) -> str:
    """Filename-friendly model tag: drop routing prefixes, keep the name."""
    for prefix in ("us.anthropic.", "global.anthropic.", "anthropic.", "openai.", "xjtlu:"):
        if model_id.startswith(prefix):
            return model_id[len(prefix):] or model_id
    return model_id


def conditions_rev() -> str:
    """Git rev of the conditions/ tree at run time — pins each trace to the
    exact prompt state it was produced under."""
    try:
        rev = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "-1", "--format=%h", "--", "conditions/"],
            text=True).strip()
        dirty = subprocess.run(
            ["git", "-C", str(ROOT), "diff", "--quiet", "--", "conditions/"]
        ).returncode != 0
        return rev + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def script_path(stem: str, lang: str) -> Path:
    hits = sorted(SCRIPTS_DIR.glob(f"{lang}/{stem}*.md"))
    if not hits:
        raise SystemExit(f"no frozen script matching {stem} under frozen-scripts/{lang}/")
    return hits[0]


def run_cell(model_id: str, sp: Path, condition: str, lang: str) -> dict:
    system = mc.load_condition(condition, lang)
    call = mc.BACKENDS[mc.backend_for(model_id)]
    user_turns = parse_script(sp)
    turns, transcript = [], []
    tag = f"{model_short(model_id)} × {condition}"
    for i, u in enumerate(user_turns, 1):
        turns.append(("user", u))
        reply = call(model_id, system, turns)   # exceptions bubble to the worker
        turns.append(("assistant", reply))
        transcript.append({"turn": i, "user": u, "assistant": reply})
        log(f"    [{tag}] turn {i}/{len(user_turns)} · {len(reply)} chars")
    return {"transcript": transcript}


def save_cell(result: dict, meta: dict) -> Path:
    OUT_DIR.mkdir(exist_ok=True)
    base = (f"{meta['script']}__{meta['model_short']}__{meta['lang']}"
            f"__{meta['condition']}__{meta['run_stamp']}")
    payload = {**meta, **result}
    (OUT_DIR / f"{base}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    L = [f"# {meta['script']} × {meta['model_short']} × {meta['condition']} ({meta['lang']})\n"]
    L.append(f"| model id | backend | conditions rev | maxTokens | run |")
    L.append(f"|---|---|---|---|---|")
    L.append(f"| `{meta['model_id']}` | {meta['backend']} | `{meta['conditions_rev']}` "
             f"| {meta['max_tokens']} | {meta['run_stamp']} |\n")
    if result.get("error"):
        L.append(f"**ERROR:** {result['error']}\n")
    for t in result.get("transcript", []):
        L.append(f"## Turn {t['turn']}\n")
        L.append(f"**User:** {t['user']}\n")
        L.append(f"**AI ({len(t['assistant'])} chars):**\n\n{t['assistant']}\n")
    (OUT_DIR / f"{base}.md").write_text("\n".join(L), encoding="utf-8")
    return OUT_DIR / f"{base}.md"


def write_index(cells: list, script: str, lang: str, stamp: str, rev: str) -> Path:
    out = OUT_DIR / f"RUN__{script}__{lang}__{stamp}.md"
    L = [f"# Matrix run — {script} ({lang})\n",
         f"Run {stamp} · conditions rev `{rev}` · maxTokens {mc.MAX_TOKENS} · "
         f"same frozen script + same condition prompts on every model.\n",
         "> Signal counts are lexical screening aids, not codes — read the cell "
         "transcripts before repeating any number.\n",
         "| model | condition | turns | total AI chars | signal hits | file |",
         "|---|---|---|---|---|---|"]
    for c in cells:
        if c.get("error"):
            L.append(f"| `{c['model_short']}` | {c['condition']} | — | — | ERROR | {c['error'][:70]} |")
            continue
        allt = "\n".join(t["assistant"] for t in c["transcript"])
        hits = mc.scan_signals(allt)
        n = sum(len(v) for v in hits.values())
        labels = ", ".join(f"{k}×{len(v)}" for k, v in hits.items()) or "—"
        L.append(f"| `{c['model_short']}` | {c['condition']} | {len(c['transcript'])} "
                 f"| {len(allt)} | {n} ({labels}) | `{c['file']}` |")
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="S2", help="frozen script stem (S1/S2/S3)")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--models", help="comma-separated; default: %s" % ",".join(DEFAULT_MODELS))
    ap.add_argument("--conditions", help="comma-separated; default: all three")
    args = ap.parse_args()

    mc.load_bedrock_key()
    log(mc.key_status())

    models = [m.strip() for m in (args.models.split(",") if args.models else DEFAULT_MODELS)]
    conditions = [c.strip() for c in (args.conditions.split(",") if args.conditions else CONDITIONS)]
    sp = script_path(args.script, args.lang)
    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    rev = conditions_rev()
    log(f"script={sp.stem} lang={args.lang} conditions_rev={rev} "
        f"models={len(models)} conditions={len(conditions)}")

    cells, lock = [], threading.Lock()

    def worker(model_id: str):
        # parallel across models; sequential across conditions within a model
        # (keeps per-provider request rate low and transcripts ordered)
        for cond in conditions:
            meta = {
                "script": sp.stem, "lang": args.lang, "condition": cond,
                "model_id": model_id, "model_short": model_short(model_id),
                "backend": mc.backend_for(model_id), "max_tokens": mc.MAX_TOKENS,
                "conditions_rev": rev, "run_stamp": stamp,
            }
            try:
                result = run_cell(model_id, sp, cond, args.lang)
            except Exception as exc:
                result = {"error": f"{type(exc).__name__}: {exc}", "transcript": []}
                log(f"    [{meta['model_short']} × {cond}] ERROR: {result['error'][:120]}")
            path = save_cell(result, meta)
            with lock:
                cells.append({**meta, **result, "file": path.name})

    threads = [threading.Thread(target=worker, args=(m,)) for m in models]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # stable order for the index: model, then condition
    cells.sort(key=lambda c: (c["model_short"], conditions.index(c["condition"])))
    idx = write_index(cells, sp.stem, args.lang, stamp, rev)
    ok = sum(1 for c in cells if not c.get("error"))
    log(f"\n{ok}/{len(cells)} cells clean · index: {idx.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
