#!/usr/bin/env python3
"""Frozen-script pilot runner.

Replays each frozen user script against each condition system prompt via
Amazon Bedrock (Converse API), saving full transcripts for manual coding
review. This is the pre-launch gate from INSTRUMENT_SPEC: do not freeze
prompts v1 until these transcripts pass the specimen-taxonomy checks.

Usage:
    python tools/frozen_pilot.py                     # all scripts x all conditions
    python tools/frozen_pilot.py --script S2 --condition supportive
    python tools/frozen_pilot.py --model us.anthropic.claude-sonnet-4-5-20250929-v1:0

Requires: pip install boto3
AWS auth: default credential chain (aws configure / SSO / env vars).

Frozen-script format: markdown files in frozen-scripts/, numbered list items
are user turns. Bracketed [...] stage directions are stripped before sending;
branch turns ("[if AI did X] say A / [if Y] say B") are resolved manually —
for the automated run we send the first branch and note it in the transcript.
"""

import argparse
import datetime
import json
import re
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
CONDITIONS_DIR = ROOT / "conditions"
SCRIPTS_DIR = ROOT / "frozen-scripts"
OUT_DIR = ROOT / "pilot-transcripts"

DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-6"
DEFAULT_REGION = "us-west-2"
TEMPERATURE = 0.7  # fixed across conditions per INSTRUMENT_SPEC R1
MAX_TOKENS = 600   # responses should be short (2-5 sentences)

CONDITIONS = ["supportive", "challenging", "neutral"]


def load_condition(name: str, lang: str = "zh") -> str:
    base = (CONDITIONS_DIR / lang / f"{name}.txt").read_text(encoding="utf-8")
    probe = (CONDITIONS_DIR / lang / "probe.txt").read_text(encoding="utf-8")
    return base + "\n" + probe


def parse_script(path: Path) -> list[str]:
    """Extract numbered user turns; strip [stage directions]; first branch wins."""
    turns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\d+)\.\s+(.*)", line.strip())
        if not m:
            continue
        text = m.group(2)
        # branch turns: "…] say A / [if …] say B" -> take text before " / ["
        if " / [" in text:
            text = text.split(" / [")[0]
        # strip stage directions
        text = re.sub(r"\[[^\]]*\]", "", text).strip()
        if text:
            turns.append(text)
    return turns


def run_one(script_path: Path, condition: str, model_id: str, region: str,
            lang: str = "zh") -> dict:
    client = boto3.client("bedrock-runtime", region_name=region)
    system_prompt = load_condition(condition, lang)
    user_turns = parse_script(script_path)

    messages = []
    transcript = []
    for i, turn in enumerate(user_turns, 1):
        messages.append({"role": "user", "content": [{"text": turn}]})
        resp = client.converse(
            modelId=model_id,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={"temperature": TEMPERATURE, "maxTokens": MAX_TOKENS},
        )
        ai_text = resp["output"]["message"]["content"][0]["text"]
        messages.append({"role": "assistant", "content": [{"text": ai_text}]})
        transcript.append({"turn": i, "user": turn, "assistant": ai_text})
        print(f"  turn {i}/{len(user_turns)} done")

    return {
        "script": script_path.stem,
        "lang": lang,
        "condition": condition,
        "model": model_id,
        "temperature": TEMPERATURE,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "transcript": transcript,
    }


def save(result: dict) -> Path:
    OUT_DIR.mkdir(exist_ok=True)
    stamp = result["timestamp"].replace(":", "-")
    out = OUT_DIR / f"{result['script']}__{result['lang']}__{result['condition']}__{stamp}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # also a readable .md for coding review
    md_lines = [f"# {result['script']} × {result['condition']}",
                f"model: {result['model']} · temp: {result['temperature']} · {result['timestamp']}", ""]
    for t in result["transcript"]:
        md_lines += [f"**U{t['turn']}:** {t['user']}", "", f"**AI:** {t['assistant']}", "", "---", ""]
    out.with_suffix(".md").write_text("\n".join(md_lines), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", help="script stem prefix, e.g. S2 (default: all)")
    ap.add_argument("--condition", choices=CONDITIONS, help="default: all")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--region", default=DEFAULT_REGION)
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    args = ap.parse_args()

    scripts = sorted((SCRIPTS_DIR / args.lang).glob("*.md"))
    if args.script:
        scripts = [s for s in scripts if s.stem.startswith(args.script)]
    conditions = [args.condition] if args.condition else CONDITIONS

    for sp in scripts:
        for cond in conditions:
            print(f"== {sp.stem} × {args.lang} × {cond} ==")
            result = run_one(sp, cond, args.model, args.region, args.lang)
            out = save(result)
            print(f"  saved {out.name}")


if __name__ == "__main__":
    main()
