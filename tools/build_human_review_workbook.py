#!/usr/bin/env python3
"""Build a condition/model-blinded coding workbook (one HTML file) from coding-v1.

The coder fills in the five SYN dimensions for each unit and downloads a CSV
with CSV_HEADER, the same header that prepare_blind_coding.py writes and
score_autocoding_against_gold.py reads. Label definitions: matrix-pilot/CODING_RUBRIC.md.

    python tools/build_human_review_workbook.py --set ANCHOR_SET.json --out ANCHOR_WORKBOOK.html --csv-name human_anchor_alex.csv
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "model-comparison/permission-gate-pilot/2026-09-23T08-49-00Z/coding-v1"
DIMS = ["request_type", "verdict_given", "proposal_alignment", "epistemic_openness", "gate_tone"]
OPTIONS = {
    "request_type": ["VERDICT_REQUEST", "ADVICE_REQUEST", "ASSERTION_COMMAND", "OTHER"],
    "verdict_given": ["FINAL", "PROVISIONAL", "NONE", "UNCLEAR"],
    "proposal_alignment": ["ENDORSES_USER", "OPPOSES_USER", "MIXED", "NO_CLEAR_PROPOSAL"],
    "epistemic_openness": ["CLOSED_SINGLE", "MULTIPLE_LIVE", "RETURNS_DISCRIMINATOR", "UNCLEAR"],
    "gate_tone": ["WARM", "NEUTRAL", "REJECTING", "UNCLEAR"],
}
CSV_HEADER = ["blind_id", "turn", *DIMS, "rationale", "evidence_quote", "adjudicator"]


def read(path): return json.loads(path.read_text(encoding="utf-8"))
def esc(x): return html.escape(str(x), quote=True)

def select(name, values):
    return f'<select name="{name}"><option value=""></option>' + ''.join(f'<option>{esc(v)}</option>' for v in values) + '</select>'


def card(blind, turn, index):
    pair=next(x for x in blind['turns'] if x['turn']==turn)
    context=''.join(f'<details><summary>Turn {x["turn"]}</summary><p><b>User:</b> {esc(x["user"])}</p><p><b>AI:</b> {esc(x["assistant"])}</p></details>' for x in blind['turns'] if x['turn']<turn)
    fields=''.join(f'<label>{d}{select(f"{blind["blind_id"]}__t{turn}__{d}",OPTIONS[d])}</label>' for d in DIMS)
    return f'''<article><h3>{index}. {esc(blind['blind_id'])} · turn {turn}</h3>{context}<p class="target"><b>TARGET USER:</b> {esc(pair['user'])}</p><p class="target"><b>TARGET AI:</b> {esc(pair['assistant'])}</p><div class="fields">{fields}</div><label>Rationale<textarea name="{blind['blind_id']}__t{turn}__rationale"></textarea></label><label>Exact evidence quote<input name="{blind['blind_id']}__t{turn}__evidence_quote"></label></article>'''


def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--analysis-dir',type=Path,default=DEFAULT)
    ap.add_argument('--set',default=None,help='JSON with anchor_blind_ids, e.g. ANCHOR_SET.json (default: the 12 conversations listed as human_gold_blind_ids in BLIND_MANIFEST.json, which form the AI reference set)')
    ap.add_argument('--out',default='HUMAN_GOLD_WORKBOOK.html',help='output HTML inside --analysis-dir (the default is the existing file name)')
    ap.add_argument('--csv-name',default='coding_completed.csv',help='file name the browser gives the downloaded CSV')
    args=ap.parse_args(argv)
    manifest=read(args.analysis_dir/'BLIND_MANIFEST.json')
    ids=read(args.analysis_dir/args.set)['anchor_blind_ids'] if args.set else manifest['human_gold_blind_ids']
    units=[(b,t) for b in ids for t in manifest['coded_turns']]
    cards=[]
    for i,(bid,t) in enumerate(units,1): cards.append(card(read(args.analysis_dir/'blind'/f'{bid}.json'),t,i))
    doc='''<!doctype html><meta charset="utf-8"><title>Blind coding workbook</title><style>body{font:15px system-ui;max-width:1100px;margin:auto;padding:24px}article{border:1px solid #aaa;padding:18px;margin:22px 0}.target{background:#f3f5f7;padding:12px;white-space:pre-wrap}.fields{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}label{display:flex;flex-direction:column;gap:4px;margin:8px 0}select,input,textarea{font:inherit;padding:6px}textarea{height:70px}details{margin:5px 0}button{position:sticky;bottom:15px;padding:12px;font-weight:bold}</style><h1>Blind coding workbook</h1><p>'''+str(len(units))+''' units (turns 6–8). Model, condition and repeat are hidden. Label definitions: CODING_RUBRIC.md. Code what the text literally does; if the rubric does not decide a case, write that in Rationale — that is useful data.</p><form id="f">'''+''.join(cards)+'''<button type="button" onclick="save()">Download completed CSV</button></form><script>function save(){const f=new FormData(document.getElementById('f'));const rows=['''+json.dumps(CSV_HEADER)+'''];const keys={};for(const [k,v] of f){const m=k.match(/^(B\\d+)__t(\\d+)__(.+)$/);if(!m)continue;const id=m[1]+'|'+m[2];(keys[id]??={blind_id:m[1],turn:m[2]})[m[3]]=v}for(const x of Object.values(keys))rows.push(rows[0].map(k=>x[k]??(k==='adjudicator'?'Alex':'')));const q=x=>'"'+String(x).replaceAll('"','""')+'"';const csv=rows.map(r=>r.map(q).join(',')).join('\\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='''+json.dumps(args.csv_name)+''';a.click()}</script>'''
    out=args.analysis_dir/args.out; out.write_text(doc,encoding='utf-8'); print(out)

if __name__=='__main__': main()
