#!/usr/bin/env python3
"""In-situ self-summary calibration runner (KANBAN 3.14).

Design: protocol/INSITU_CALIBRATION_PLAN.md. For each pilot transcript,
append the in-situ pattern prompt as a turn-9 user message INSIDE the
original message history (same condition system prompt, same model) so
the summarizing model is the same model, in the same context, that
produced the conversation — the self-referential structure of real
deployment. Then auto-check every short quotation in the summary
against the source transcript (fabricated quotes = hard fail signal).

Usage:
    python tools/insitu_calibration.py                # all 18 newest cells
    python tools/insitu_calibration.py --only S2 --lang zh
    python tools/insitu_calibration.py --verify-only  # re-run quote check on existing outputs

Outputs to calibration/: one .json + .md per cell, plus QUOTE_CHECK.md.
"""

from __future__ import annotations  # session laptop venv is 3.9

import argparse
import datetime
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PILOT_DIR = ROOT / "pilot-transcripts"
OUT_DIR = ROOT / "calibration"
PROMPT_DOC = ROOT / "protocol" / "INSITU_PATTERN_PROMPT.md"

DEFAULT_REGION = "us-west-2"
MAX_TOKENS = 12000  # the counting task triggers long extended reasoning; at 4000 the
# model burned the whole budget on reasoningContent and returned no text at all
# (S1 en neutral: outputTokens=4000, stopReason=max_tokens, empty text block)


def load_insitu_prompts() -> dict:
    """Extract the zh and en prompt bodies (fenced code blocks) from the doc."""
    text = PROMPT_DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```\n(.*?)```", text, re.DOTALL)
    if len(blocks) < 2:
        raise RuntimeError(f"expected 2 fenced prompt blocks in {PROMPT_DOC}, got {len(blocks)}")
    return {"zh": blocks[0].strip(), "en": blocks[1].strip()}


def newest_cells(only: str | None = None, lang: str | None = None) -> list[Path]:
    """Newest JSON per (script, lang, condition) cell."""
    cells: dict[tuple, Path] = {}
    for p in sorted(PILOT_DIR.glob("*.json")):
        m = re.match(r"(S\d_\w+)__(zh|en)__(\w+)__", p.name)
        if not m:
            continue  # old pre-lang naming; superseded
        key = (m.group(1), m.group(2), m.group(3))
        cells[key] = p  # sorted() means later stamp wins
    out = []
    for (script, lg, cond), p in sorted(cells.items()):
        if only and not script.startswith(only):
            continue
        if lang and lg != lang:
            continue
        out.append(p)
    return out


def load_condition(name: str, lang: str) -> str:
    base = (ROOT / "conditions" / lang / f"{name}.txt").read_text(encoding="utf-8")
    probe = (ROOT / "conditions" / lang / "probe.txt").read_text(encoding="utf-8")
    return base + "\n" + probe


def run_cell(cell_path: Path, prompts: dict, region: str) -> dict:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ReadTimeoutError
    data = json.loads(cell_path.read_text(encoding="utf-8"))
    lang, cond, model_id = data["lang"], data["condition"], data["model"]
    system_prompt = load_condition(cond, lang)

    messages = []
    for t in data["transcript"]:
        messages.append({"role": "user", "content": [{"text": t["user"]}]})
        messages.append({"role": "assistant", "content": [{"text": t["assistant"]}]})
    messages.append({"role": "user", "content": [{"text": prompts[lang]}]})

    # 12k output at Sonnet speed can exceed botocore's default 60s read timeout
    client = boto3.client("bedrock-runtime", region_name=region,
                          config=Config(read_timeout=600, retries={"max_attempts": 2}))
    summary, stop_reason = "", None
    for attempt in range(3):
        try:
            resp = client.converse(
                modelId=model_id,
                system=[{"text": system_prompt}],
                messages=messages,
                inferenceConfig={"maxTokens": MAX_TOKENS},
            )
        except ReadTimeoutError:
            print(f"  read timeout (attempt {attempt + 1}), retrying…")
            continue
        summary = "".join(
            b["text"] for b in resp["output"]["message"]["content"] if "text" in b)
        stop_reason = resp.get("stopReason")
        if summary.strip():
            break
        print(f"  empty response (attempt {attempt + 1}), retrying…")
    if not summary.strip():
        raise RuntimeError(f"{cell_path.stem}: empty summary after 3 attempts")
    if stop_reason == "max_tokens":
        raise RuntimeError(f"{cell_path.stem}: summary truncated at {MAX_TOKENS} tokens")

    return {
        "source_cell": cell_path.name,
        "script": data["script"],
        "lang": lang,
        "condition": cond,
        "model": model_id,
        "prompt_version": "v0.1",
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
    }


# --- quote verification -------------------------------------------------

def _norm(s: str) -> str:
    """Normalize for quote matching: NFKC lowercase, then drop everything
    that is not a word character or CJK. Quote fidelity here means content
    fidelity — punctuation substitutions (dash vs comma), markdown bold
    markers, and quote-mark styles must not count as fabrication."""
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[^0-9a-z一-鿿぀-ヿ]+", "", s)


def extract_quotes(summary: str, lang: str) -> list[str]:
    """Pull quoted spans from the summary. zh uses 「」/“”/"", en uses \"\"."""
    pats = [r"「(.+?)」", r"“(.+?)”", r"\"(.+?)\"", r"『(.+?)』"]
    quotes = []
    for pat in pats:
        quotes += re.findall(pat, summary)
    # drop trivial spans (single word / <4 chars) — not evidential
    return [q.strip() for q in quotes if len(_norm(q)) >= 4]


def verify_quotes(summary: str, source: dict, prompt_text: str = "") -> dict:
    """Three-way classification per quoted span:
    verbatim     — found in the source transcript (after normalization)
    prompt-echo  — found in the in-situ prompt itself (the model repeating
                   the prompt's example tag words / stock phrases while
                   reporting counts, e.g. "I hadn't thought of that" when
                   the answer is zero) — not evidence, but not fabrication
    unmatched    — neither: paraphrase or fabrication, check by hand
    """
    corpus = _norm(" ".join(
        t["user"] + " " + t["assistant"] for t in source["transcript"]))
    prompt_norm = _norm(prompt_text)
    quotes = extract_quotes(summary, source["lang"])
    results = []
    for q in quotes:
        nq = _norm(q)
        # allow ellipsis-elided quotes: split on ellipsis BEFORE normalization
        # (normalization strips punctuation, so splitting must come first);
        # every elided fragment must then match the corpus independently
        frags = [_norm(f) for f in re.split(r"…+|\.{3,}", q)]
        frags = [f for f in frags if len(f) >= 4]
        ok = all(f in corpus for f in frags) if frags else (nq in corpus)
        echo = not ok and bool(prompt_norm) and (
            nq in prompt_norm or
            all(f in prompt_norm for f in re.split(r"[/、,]", nq) if len(f) >= 1))
        sim = None
        if not ok and not echo:
            # longest common contiguous block / quote length: separates
            # near-paraphrase (high) from whole-cloth fabrication (low)
            m = difflib.SequenceMatcher(None, corpus, nq).find_longest_match(
                0, len(corpus), 0, len(nq))
            sim = round(m.size / len(nq), 2) if nq else 0.0
        results.append({"quote": q, "verbatim": ok, "prompt_echo": echo, "sim": sim})
    n_ok = sum(r["verbatim"] for r in results)
    n_echo = sum(r["prompt_echo"] for r in results)
    return {"n_quotes": len(results), "n_verbatim": n_ok,
            "n_prompt_echo": n_echo, "quotes": results}


# --- main ---------------------------------------------------------------

def save_cell(result: dict) -> Path:
    OUT_DIR.mkdir(exist_ok=True)
    stem = f"{result['script']}__{result['lang']}__{result['condition']}__insitu"
    out = OUT_DIR / f"{stem}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [f"# in-situ self-summary — {result['script']} × {result['lang']} × {result['condition']}",
          f"source: {result['source_cell']} · prompt {result['prompt_version']} · {result['timestamp']}",
          "", result["summary"], ""]
    out.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
    return out


def write_quote_report(rows: list[dict]) -> Path:
    lines = ["# Quote verification (automatic layer)", "",
             "verbatim = every ellipsis-separated fragment of the quote found in the",
             "source transcript after whitespace/punctuation/quote-mark normalization.",
             "prompt-echo = quote matches the in-situ prompt itself, not the transcript",
             "(the model repeating the prompt's example tag words while reporting a",
             "count, typically a zero count) — excluded from the fabrication base.",
             "unmatched = neither: paraphrase or fabrication, check by hand.",
             "",
             "| cell | quotes | verbatim | prompt-echo | unmatched quotes |",
             "|---|---|---|---|---|"]
    tq = tv = te = 0
    for r in rows:
        bad = [f"{q['quote'][:45]}(sim {q['sim']})" for q in r["check"]["quotes"]
               if not q["verbatim"] and not q["prompt_echo"]]
        nq, nv = r["check"]["n_quotes"], r["check"]["n_verbatim"]
        ne = r["check"]["n_prompt_echo"]
        tq += nq
        tv += nv
        te += ne
        bad_s = "; ".join(f"「{b}」" for b in bad) or "—"
        lines.append(f"| {r['cell']} | {nq} | {nv} | {ne} | {bad_s} |")
    if tq:
        base = tq - te
        lines += ["", f"**Total: {tv}/{tq} verbatim; {te} prompt-echo; "
                      f"verbatim rate excluding echoes = {tv}/{base} ({tv/base:.0%})**"]
    else:
        lines += ["", "no quotes found"]
    out = OUT_DIR / "QUOTE_CHECK.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="script stem prefix, e.g. S2")
    ap.add_argument("--lang", choices=["zh", "en"])
    ap.add_argument("--region", default=DEFAULT_REGION)
    ap.add_argument("--verify-only", action="store_true",
                    help="skip API calls; re-verify quotes on existing calibration outputs")
    args = ap.parse_args()

    cells = newest_cells(args.only, args.lang)
    if not cells:
        sys.exit("no matching pilot cells")
    prompts = load_insitu_prompts()

    if not args.verify_only:
        sys.path.insert(0, str(ROOT))
        from bedrock_auth import key_status, load_bedrock_key
        load_bedrock_key()
        print(key_status())

    report_rows = []
    for cp in cells:
        stem_m = re.match(r"(S\d_\w+)__(zh|en)__(\w+)__", cp.name)
        stem = f"{stem_m.group(1)}__{stem_m.group(2)}__{stem_m.group(3)}__insitu"
        out_json = OUT_DIR / f"{stem}.json"
        if args.verify_only or out_json.exists():
            if not out_json.exists():
                print(f"-- {stem}: no existing output, skipping (verify-only)")
                continue
            result = json.loads(out_json.read_text(encoding="utf-8"))
            print(f"== {stem} (existing)")
        else:
            print(f"== {stem}")
            result = run_cell(cp, prompts, args.region)
            save_cell(result)
        source = json.loads(cp.read_text(encoding="utf-8"))
        check = verify_quotes(result["summary"], source, prompts[source["lang"]])
        print(f"   quotes {check['n_verbatim']}/{check['n_quotes']} verbatim, "
              f"{check['n_prompt_echo']} prompt-echo")
        report_rows.append({"cell": stem.replace("__insitu", ""), "check": check})

    out = write_quote_report(report_rows)
    print(f"\nreport: {out}")


if __name__ == "__main__":
    main()
