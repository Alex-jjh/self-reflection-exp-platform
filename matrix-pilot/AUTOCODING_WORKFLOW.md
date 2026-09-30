# Auto-coding workflow v2 — synthetic matrix (SYN)

> **Summary:** How `tools/run_matrix_autocoding.py` codes AI turns 6–8 of the 60 frozen SYN conversations: Jev plus a slow coder and a judge from the other provider family, all blind to generator and condition. The generative coders receive the rubric's coding sections (definitions, decision rules, hard cases) but not its routing and reliability text. Every output folder is hash-locked and keeps the exact rubric text its coders received, so codes made under different instructions are never mixed.

## Goal

Code AI turns 6–8 of the 60 frozen conversations (180 units) without showing
coders the generator model, condition or repeat. Model agreement is not
accuracy; what accuracy is computed against is stated in `CODING_RUBRIC.md`
(Evidence and reliability).

## Coders

1. **Fast coder:** Jev 1.13 (`jev-1.13.0`), typed choices with calibrated
   confidence. Jev receives one short criterion per label (`jev_questions()` in
   the script), not the rubric text. These criteria paraphrase the label
   definitions and do not contain the v2.1 decision rules.
2. **Slow coder:** a generative model from the other provider family than the
   model that generated the conversation. Its system prompt contains the
   rubric's coder text: the sections "Why v2" and "Dimensions" of the rubric
   file (`--rubric`, default `CODING_RUBRIC.md`), marked in its source by
   `<!-- coder-text:start -->` and `<!-- coder-text:end -->`, with every
   definition, decision rule and hard case.
3. **Judge:** another model from that same other family, called when the rules
   under Escalation apply. It receives the same coder text, and sees Jev's
   labels and probabilities and the slow coder's code.
4. **Human queue:** unresolved or low-quality cases; nothing is dropped.

Bedrock access gives only two generative provider families, so the judge is a
different model but not a third independent family.

## Generator-aware routing (hidden from coder prompts)

| Generator | Slow coder | Judge |
|---|---|---|
| Claude Sonnet 5, Claude Haiku 4.5 (Anthropic) | GPT-5.6 terra | GPT-5.6 luna |
| GPT-5.6 sol (OpenAI) | Claude Haiku 4.5 | Claude Sonnet 4.6 |

Model IDs are in `ROUTING` in the script. Claude Haiku 4.5 is also one of the
three generators; as a coder it only sees GPT-5.6 sol output.

## Labels

For each of turns 6–8, code five independent dimensions (full definitions in
`CODING_RUBRIC.md`): request type; whether the AI gives a final, provisional or
no verdict; whether it endorses or opposes the user's proposal; whether the
response closes the space, keeps several possibilities live, or returns a
discriminator; and tone. **Giving a verdict and agreeing with the user's answer
are separate.**

## Escalation

Judge if Jev confidence is below .80 or Jev and slow coder disagree on one of
the three load-bearing dimensions (verdict given / proposal alignment /
epistemic openness), or if the slow coder's evidence is not an exact source
substring after quote/whitespace normalization. Request-type and tone
disagreements are retained as process data but do not alone trigger a judge.
Human queue if parsing ultimately fails, judge remains unclear/low-confidence,
or judge evidence is invalid. Every attempt, including format repairs, keeps its
raw text, parse result and stop reason.

## Blinding

`tools/prepare_blind_coding.py` verifies every frozen conversation checksum
before creating `B###.json` files. A coder request contains the blind transcript
of the unit and the rubric's coder text; the judge also gets the other coders'
labels. The unit part contains no blind ID, model, condition or mapping.

The rest of the rubric is not sent. Its routing paragraph says that a
generator's provider family never codes its own output; with only two families,
a coder that read it could infer the generator's family. Its reliability and
version sections name the human-anchor coder, the adjudicator and the reference
records. The runner refuses a rubric without the two markers, and refuses coder
text that names a provider family, a model, Jev, Alex or Brennan, a condition,
the unblinded read, the AI reference or the human anchor (`CODER_TEXT_FORBIDDEN`
in the script).

The rubric's hard cases (B026 t8, B030 t8, B042 t7 and t8, B048 t8) name five
units of the AI reference by blind ID, quote them and give their codes. A coder
is therefore not independent of the AI reference on those five units. The coder
is not told the blind ID of the unit it codes, and a blind ID does not reveal
the generator or condition. None of the five is a human-anchor unit
(`coding-v1/ANCHOR_SET.json`).

`prepare_blind_coding.py` also selects one conversation per 3×2×2 cell. In
`coding-v1` these 12 conversations are the AI reference set; their IDs are
listed under the key `human_gold_blind_ids` in `BLIND_MANIFEST.json`.

## Output files

All paths are inside the analysis folder (`--analysis-dir`, default
`model-comparison/permission-gate-pilot/2026-09-23T08-49-00Z/coding-v1/`).

| File | Content |
|---|---|
| `<codes-dir>/B###__tN.json` | Public record, schema 2: blind ID, turn, `rubric_path`, `rubric_version`, `rubric_sha256` (the rubric file), `rubric_coder_text_sha256` (the text sent to the coders), `script_sha256`; Jev's labels, confidences and probabilities; slow coder and judge codes, rationales and every raw attempt; routing decisions (`judge_triggered`, `judge_reasons`); `final`; human-queue flags. |
| `<codes-dir>/CODING_LOCK.json` | SHA-256 of the script, the rubric file, this document, `BLIND_MANIFEST.json` and the coder text, written when the folder is first used. |
| `<codes-dir>/CODER_RUBRIC_<first 12 hex digits of its SHA-256>.md` | The exact coder text sent to the slow coder and judge. A folder re-locked with `--force-recode` under a changed coder text keeps one file per text, so every record's `rubric_coder_text_sha256` names a file in the folder. |
| `<codes-dir>/SUMMARY.json` | Run statistics over the records whose hashes match the current script and rubric, plus the number of stale records. |
| `private_routing/<codes-dir name>/B###__tN.json` | Private sidecar: generator family, slow coder and judge model and family, and per-request gateway metadata (request hash, token usage, latency). `private_routing/` contains a `.gitignore` that ignores the folder. |

The coder model, token counts and latency identify the coder's provider family
and therefore the generator's, so they stay out of the public record. Nothing
downstream reads the sidecar: `tools/score_autocoding_against_gold.py` reads only
the public records and the folder's lock, and an unblinded analysis joins on
blind ID with `private_mapping.json`.

## Reruns and locks

- Every run writes into `--codes-dir`, a folder inside the analysis folder
  (default `autocodes`; `calibration` with `--calibration`). A rerun under a new
  rubric or script needs a new folder name, e.g. `autocodes-v2.1`.
- A run continues in an existing folder only if all four hashes in its
  `CODING_LOCK.json` match. Editing the script, the rubric, this document or the
  manifest therefore closes the folder to further runs.
- An existing unit record is reused only if its `rubric_sha256` and
  `script_sha256` match the current files. Otherwise the run stops before any
  model call and asks for a new `--codes-dir`.
- `--force-recode` recodes every selected unit and re-locks the folder to the
  current hashes. Records of units that were not selected keep their old hashes:
  the runner's `SUMMARY.json` counts them as stale, the next run without
  `--force-recode` refuses the folder, and the scorer leaves them out and lists
  them under `stale_units_excluded`. A folder that holds records but no lock
  (`coding-v1/autocodes/` and the `coding-v1/calibration*/` folders) is never
  written to, even with `--force-recode`; the scorer scores such a folder as it
  is.
- `--rubric` must have the coder-text markers. `CODING_RUBRIC_v2.md` has none: it
  is the frozen text of the v1 run, whose coders received label names only.
- Gateway and Jev credentials are needed only if a unit has to be coded; a
  complete folder is re-summarized with no model calls.
- The gateway contract is in `README.md` (Run). Its launcher passes extra
  arguments through to the script and defaults to calibration mode, so give
  `--codes-dir` explicitly.

Example: code the four human-anchor conversations into a new folder, then
compare them with a completed CSV.

```bash
.venv/bin/python tools/run_matrix_autocoding.py --blind-ids B004,B022,B040,B047 --codes-dir autocodes-anchor-v2.1
.venv/bin/python tools/score_autocoding_against_gold.py --codes-dir autocodes-anchor-v2.1 --reference human_anchor_alex.csv
```

## Versions

| Workflow | Data coded with it | How it differs from v2 |
|---|---|---|
| v1: `AUTOCODING_WORKFLOW_v1.md`, the exact text hashed in `coding-v1/AUTOCODING_LOCK.json` (script and text from git commit `5a0f70c`) | `coding-v1/autocodes/` (180 units, rubric v2, kept as `CODING_RUBRIC_v2.md`) | The slow coder and judge received label names only, not the rubric text. Public records contain generator family, coder models and request metadata, and carry no rubric or script hash. There was no folder lock, and a rerun into the same folder returned the existing records without coding. The v1 text names Claude Opus 5 as the slow coder for GPT-5.6 sol output; the code and the 60 records of GPT-5.6 sol units used Claude Haiku 4.5. |
| v2: this document | none yet | — |
