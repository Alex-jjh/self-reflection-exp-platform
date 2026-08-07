#!/usr/bin/env python3
"""In-situ prompt v1 real-world test (3.14 extension arm).

Runs the v1 pattern-extraction prompt against REAL long conversations
from the private corpus (Conversation/, gitignored, never committed),
appending it as the next user turn inside the original message history
so the summarizing model is the family that produced the conversation
(Gemini summarizing Gemini) — the same self-referential structure the
calibration reproduced for Claude. Covers the two calibration limits:
real long dialogues (23-64 user turns vs 8-turn scripts) and a second
model family.

PRIVACY: output goes to Conversation/insitu-test/ (outside all repos).
Nothing from the corpus is written into any git-tracked path.

Usage:
    python tools/insitu_realworld_test.py            # C7 + C8
    python tools/insitu_realworld_test.py --file <path.json>
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONV_DIR = ROOT.parent / "Conversation"
OUT_DIR = CONV_DIR / "insitu-test"
PROMPT_DOC = ROOT / "protocol" / "INSITU_PATTERN_PROMPT.md"

GEMINI_MODEL = "gemini-3.6-flash"
MAX_TOKENS = 30000  # long conversations need generous reasoning + output room

# default = the corpus conversations that already have a human close-read
# coding file (CODING_*.md) to compare against; matched by stem, so no
# conversation titles are hardcoded here
def default_files() -> list:
    out = []
    coded_stems = [p.stem for p in CONV_DIR.glob("CODING_*.md")]
    for j in sorted(CONV_DIR.glob("Gemini-*.json")):
        topic = j.stem.split("-", 1)[1].rsplit("-2026", 1)[0]
        if any(topic[:6] in c for c in coded_stems):
            out.append(j)
    return out

sys.path.insert(0, str(ROOT / "tools"))
from insitu_calibration import _norm, extract_quotes, load_insitu_prompts  # noqa: E402


def load_conversation(path: Path) -> list:
    """Corpus format: list of {role: user|assistant/model, content: str}."""
    data = json.loads(path.read_text(encoding="utf-8"))
    turns = []
    for m in data:
        role = "user" if m["role"] == "user" else "model"
        text = m["content"]
        # ChatGPT-export style prefix seen in the corpus
        text = re.sub(r"^You said\s+", "", text)
        turns.append((role, text))
    return turns


def call_gemini_history(turns: list, prompt: str) -> str:
    from model_compare import load_gemini_key  # handles '#' comment lines
    key = load_gemini_key()
    if not key:
        raise RuntimeError("no .gemini_key")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    contents = [types.Content(role=r, parts=[types.Part(text=t)]) for r, t in turns]
    contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
    import time
    last = None
    for _ in range(4):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL, contents=contents,
                config=types.GenerateContentConfig(max_output_tokens=MAX_TOKENS))
            return resp.text or ""
        except Exception as exc:
            last = exc
            if "RESOURCE_EXHAUSTED" not in str(exc):
                raise
            m = re.search(r"retry in ([0-9.]+)s", str(exc))
            time.sleep(float(m.group(1)) + 2 if m else 30)
    raise last


def verify_quotes_local(summary: str, turns: list, prompt: str) -> dict:
    corpus = _norm(" ".join(t for _, t in turns))
    pnorm = _norm(prompt)
    out = []
    for q in extract_quotes(summary, "zh"):
        frags = [_norm(f) for f in re.split(r"…+|\.{3,}", q)]
        frags = [f for f in frags if len(f) >= 4]
        nq = _norm(q)
        ok = all(f in corpus for f in frags) if frags else (nq in corpus)
        echo = not ok and nq in pnorm
        out.append({"quote": q, "verbatim": ok, "prompt_echo": echo})
    return {"n": len(out), "verbatim": sum(r["verbatim"] for r in out),
            "echo": sum(r["prompt_echo"] for r in out), "quotes": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", help="conversation json path")
    args = ap.parse_args()
    files = [Path(f) for f in args.file] if args.file else default_files()

    prompts = load_insitu_prompts()
    OUT_DIR.mkdir(exist_ok=True)

    for path in files:
        turns = load_conversation(path)
        n_user = sum(1 for r, _ in turns if r == "user")
        print(f"== {path.stem} ({len(turns)} msgs, {n_user} user turns)")
        summary = call_gemini_history(turns, prompts["zh"])
        check = verify_quotes_local(summary, turns, prompts["zh"])
        stamp = datetime.datetime.now().isoformat(timespec="seconds").replace(":", "-")
        out = OUT_DIR / f"{path.stem}__insitu-v1__{GEMINI_MODEL}__{stamp}.md"
        out.write_text(
            f"# in-situ v1 real-world test — {path.stem}\n"
            f"model: {GEMINI_MODEL} (self-summary, in-context) · prompt v1 zh · {stamp}\n"
            f"quote check: {check['verbatim']}/{check['n']} verbatim, {check['echo']} prompt-echo\n"
            f"non-verbatim: {[r['quote'][:40] for r in check['quotes'] if not r['verbatim'] and not r['prompt_echo']]}\n\n"
            "---\n\n" + summary, encoding="utf-8")
        print(f"   quotes {check['verbatim']}/{check['n']} verbatim, "
              f"{check['echo']} echo -> {out.name}")


if __name__ == "__main__":
    main()
